import asyncio
import json
import sys
import threading
from typing import Any, Callable, Optional, Dict, List
import os
from dotenv import find_dotenv, load_dotenv

import requests
from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceExpiredSession

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("salesforce")


def log(message: str) -> None:
    """Logs to stderr: stdout is reserved for the MCP JSON-RPC stream."""
    print(message, file=sys.stderr, flush=True)


def load_environment() -> None:
    """Loads credentials from a .env file.

    Looks at MCP_SALESFORCE_ENV_FILE first, then walks up from the working
    directory, then from the package itself. Existing environment variables
    always win, so an MCP client config keeps priority over any file.
    """
    explicit = os.getenv('MCP_SALESFORCE_ENV_FILE')
    if explicit:
        if not load_dotenv(explicit):
            log(f"MCP_SALESFORCE_ENV_FILE={explicit} could not be read.")
        return
    load_dotenv(find_dotenv(usecwd=True))
    load_dotenv()


load_environment()


class SalesforceAuthError(Exception):
    """Raised when no usable Salesforce session can be obtained."""


def resolve_login_url(domain: Optional[str]) -> str:
    """Builds the base URL used for authentication.

    Accepts a full URL, the classic `login`/`test` shortcuts, a full host
    (`acme.my.salesforce.com`) or a My Domain prefix (`acme`, `acme--uat.sandbox.my`).
    """
    value = (domain or 'test').strip().rstrip('/')
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value in ('login', 'test'):
        return f"https://{value}.salesforce.com"
    if value.endswith('.salesforce.com') or value.endswith('.force.com'):
        return f"https://{value}"
    if value.endswith('.my'):
        return f"https://{value}.salesforce.com"
    return f"https://{value}.my.salesforce.com"


def format_sobject_metadata_for_llm(metadata: Dict) -> str:
    """Format the metadata for optimal use with an LLM."""
    output = ""
    # output += f"# {metadata['object_name']} ({metadata['label']})\n\n"
    # output += "Fields\n\n"
    
    for field in metadata['fields']:
        output += f"{field.get('name', '')} : {field.get('label', '')}\n"
        output += f"- Type: {field.get('type', '')}({field.get('length', '')})"
        if field.get('type') == 'reference':
            output += f" to {', '.join(field.get('referenceTo', []))}"
            output += f" via {field['relationshipName']}"
            output += "\n"
        else:
            output += "\n"
        if field.get('description'):
            output += f"- Description: {field['description']}\n"
        if field.get('required'):
            output += "- Required: Yes\n"
        if field.get('picklistValues'):
            values = ', '.join([v['value'] for v in field['picklistValues']])
            output += f"- Possible values: {values}\n"
        output += "\n"
    
    return output


class SalesforceClient:
    """Handles Salesforce authentication, operations and caching."""

    def __init__(self):
        self.sf: Optional[Salesforce] = None
        self.sobjects_cache: dict[str, Any] = {}
        self.auth_flow: Optional[str] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()

    def _selected_flow(self) -> str:
        """Determines which OAuth flow to use, from the environment."""
        explicit = (os.getenv('SALESFORCE_AUTH_FLOW') or '').strip().lower()
        if explicit:
            if explicit not in ('client_credentials', 'password'):
                raise SalesforceAuthError(
                    f"Unknown SALESFORCE_AUTH_FLOW '{explicit}': "
                    "expected 'client_credentials' or 'password'."
                )
            return explicit
        if os.getenv('SALESFORCE_CLIENT_ID') and os.getenv('SALESFORCE_CLIENT_SECRET'):
            return 'client_credentials'
        if os.getenv('SALESFORCE_USERNAME') and os.getenv('SALESFORCE_PASSWORD'):
            return 'password'
        raise SalesforceAuthError(
            "No Salesforce credentials found. Set SALESFORCE_CLIENT_ID and "
            "SALESFORCE_CLIENT_SECRET (client credentials flow) along with "
            "SALESFORCE_INSTANCE_URL."
        )

    def _connect_client_credentials(self, login_url: str) -> Salesforce:
        """OAuth 2.0 client credentials flow.

        Requires a connected app with 'Enable Client Credentials Flow' checked and a
        run-as user, and a My Domain URL: login.salesforce.com / test.salesforce.com
        do not serve this grant.
        """
        client_id = os.getenv('SALESFORCE_CLIENT_ID')
        client_secret = os.getenv('SALESFORCE_CLIENT_SECRET')
        token_url = f"{login_url}/services/oauth2/token"
        try:
            response = requests.post(
                token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise SalesforceAuthError(f"Token request to {token_url} failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError:
            raise SalesforceAuthError(
                f"Token endpoint {token_url} returned a non-JSON response "
                f"(HTTP {response.status_code}). Check SALESFORCE_INSTANCE_URL."
            ) from None

        if response.status_code != 200 or 'access_token' not in payload:
            error = payload.get('error', f"HTTP {response.status_code}")
            description = payload.get('error_description', '')
            raise SalesforceAuthError(
                f"Client credentials flow rejected by {token_url}: {error} {description}".strip()
            )

        kwargs: Dict[str, Any] = {
            'instance_url': payload.get('instance_url', login_url),
            'session_id': payload['access_token'],
        }
        version = os.getenv('SALESFORCE_API_VERSION')
        if version:
            kwargs['version'] = version
        return Salesforce(**kwargs)

    def _connect_password(self, domain: str) -> Salesforce:
        """Legacy SOAP username/password login, kept for backward compatibility."""
        kwargs: Dict[str, Any] = {
            'domain': domain,
            'username': os.getenv('SALESFORCE_USERNAME'),
            'password': os.getenv('SALESFORCE_PASSWORD'),
            'security_token': os.getenv('SALESFORCE_SECURITY_TOKEN'),
        }
        version = os.getenv('SALESFORCE_API_VERSION')
        if version:
            kwargs['version'] = version
        return Salesforce(**kwargs)

    def connect(self, force: bool = False) -> bool:
        """Establishes (or refreshes) the connection to Salesforce.

        Returns:
            bool: True if connection successful, False otherwise
        """
        with self._lock:
            if self.sf is not None and not force:
                return True
            try:
                flow = self._selected_flow()
                raw_domain = os.getenv('SALESFORCE_INSTANCE_URL')
                if flow == 'client_credentials':
                    login_url = resolve_login_url(raw_domain)
                    log(f"Salesforce auth: client credentials flow on {login_url}")
                    self.sf = self._connect_client_credentials(login_url)
                else:
                    domain = raw_domain
                    if domain is None:
                        domain = 'test'
                    elif domain not in ['login', 'test'] and not domain.endswith('.my'):
                        domain = f"{domain}.my"
                    log(f"Salesforce auth: username/password (SOAP) flow on domain {domain}")
                    self.sf = self._connect_password(domain)
                self.auth_flow = flow
                self.last_error = None
                return True
            except Exception as e:
                self.sf = None
                self.last_error = str(e)
                log(f"Salesforce connection failed: {self.last_error}")
                return False

    def ensure_connection(self) -> Salesforce:
        """Returns a live Salesforce session, connecting lazily if needed."""
        if self.sf is None and not self.connect():
            raise SalesforceAuthError(
                self.last_error or "Salesforce connection not established."
            )
        return self.sf

    def call(self, action: Callable[[Salesforce], Any]) -> Any:
        """Runs an API call, re-authenticating once if the session has expired."""
        sf = self.ensure_connection()
        try:
            return action(sf)
        except SalesforceExpiredSession:
            log("Salesforce session expired, re-authenticating.")
            if not self.connect(force=True):
                raise SalesforceAuthError(
                    self.last_error or "Salesforce re-authentication failed."
                )
            return action(self.sf)

    def get_object_fields(self, object_name: str) -> str:
        """Retrieves field Names, labels and types for a specific Salesforce object.
        if there is a lookup, the type is reference.
        - Type: `reference(18)` to LookupTable via LookupField

        Args:
            object_name (str): The name of the Salesforce object.

        Returns:
            str: a markdown formatted string with the object fields.
        """
        response = self.call(lambda sf: sf.restful(f'sobjects/{object_name}/describe'))
        return format_sobject_metadata_for_llm(response)


sf_client = SalesforceClient()


@mcp.tool()
async def run_soql_query(query: str) -> str:
    """Executes a SOQL query against Salesforce.
    Args:
        query: The SOQL query to execute
        
    When using this tool, always use a column name in the query. 
    It is important when you aggregate or count. 
    In this case use the Id column. example:  select count(Id) from Account
    """
    try:
        results = sf_client.call(lambda sf: sf.query_all(query))
        return f"SOQL Query Results:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error executing SOQL query: {str(e)}"

@mcp.tool()
async def run_sosl_search(search: str) -> str:
    """Executes a SOSL search against Salesforce.
    Args:
        search: The SOSL search to execute (e.g., 'FIND {John Smith} IN ALL FIELDS')
    """
    try:
        results = sf_client.call(lambda sf: sf.search(search))
        return f"SOSL Search Results:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error executing SOSL search: {str(e)}"

@mcp.tool()
async def get_sobject_fields(object_name: str) -> str:
    """Retrieves field Names, labels and types for a specific Salesforce object.
        if there is a lookup, the type is reference with the lookup table name and the fields name.

    Args:
        object_name: The name of the Salesforce object (e.g., 'Account', 'Contact')
    """
    try:
        return sf_client.get_object_fields(object_name)
    except Exception as e:
        return f"Error retrieving object fields: {str(e)}"

@mcp.tool()
async def get_record(object_name: str, record_id: str) -> str:
    """Retrieves a specific record by ID.
    Args:
        object_name: The name of the Salesforce object (e.g., 'Account', 'Contact')
        record_id: The ID of the record to retrieve
    """
    try:
        results = sf_client.call(lambda sf: getattr(sf, object_name).get(record_id))
        return f"{object_name} Record:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error retrieving record: {str(e)}"

@mcp.tool()
async def create_record(object_name: str, data: Dict[str, Any]) -> str:
    """Creates a new record.
    Args:
        object_name: The name of the Salesforce object (e.g., 'Account', 'Contact')
        data: The data for the new record
    """
    try:
        results = sf_client.call(lambda sf: getattr(sf, object_name).create(data))
        return f"Create {object_name} Record Result:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error creating record: {str(e)}"

@mcp.tool()
async def update_record(object_name: str, record_id: str, data: Dict[str, Any]) -> str:
    """Updates an existing record.
    Args:
        object_name: The name of the Salesforce object (e.g., 'Account', 'Contact')
        record_id: The ID of the record to update
        data: The updated data for the record
    """
    try:
        results = sf_client.call(lambda sf: getattr(sf, object_name).update(record_id, data))
        return f"Update {object_name} Record Result: {results}"
    except Exception as e:
        return f"Error updating record: {str(e)}"

@mcp.tool()
async def delete_record(object_name: str, record_id: str) -> str:
    """Deletes a record.
    Args:
        object_name: The name of the Salesforce object (e.g., 'Account', 'Contact')
        record_id: The ID of the record to delete
    """
    try:
        results = sf_client.call(lambda sf: getattr(sf, object_name).delete(record_id))
        return f"Delete {object_name} Record Result: {results}"
    except Exception as e:
        return f"Error deleting record: {str(e)}"

@mcp.tool()
async def tooling_execute(action: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> str:
    """Executes a Tooling API request.
    Args:
        action: The Tooling API endpoint to call (e.g., 'sobjects/ApexClass')
        method: The HTTP method (default: 'GET')
        data: Data for POST/PATCH requests
    """
    try:
        results = sf_client.call(lambda sf: sf.toolingexecute(action, method=method, data=data))
        return f"Tooling Execute Result:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error executing tooling request: {str(e)}"

@mcp.tool()
async def apex_execute(action: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> str:
    """Executes an Apex REST request.
    Args:
        action: The Apex REST endpoint to call (e.g., '/MyApexClass')
        method: The HTTP method (default: 'GET')
        data: Data for POST/PATCH requests
    """
    try:
        results = sf_client.call(lambda sf: sf.apexecute(action, method=method, data=data))
        return f"Apex Execute Result:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error executing Apex request: {str(e)}"

@mcp.tool()
async def restful(path: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> str:
    """Makes a direct REST API call to Salesforce.
    Args:
        path: The path of the REST API endpoint (e.g., 'sobjects/Account/describe')
        method: The HTTP method (default: 'GET')
        params: Query parameters for the request
        data: Data for POST/PATCH requests
    """
    try:
        results = sf_client.call(lambda sf: sf.restful(path, method=method, params=params, json=data))
        return f"RESTful API Call Result:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error making REST API call: {str(e)}"



def main():
    connected = sf_client.connect()
    log(f"Connected: {connected}")
    if not connected:
        # Not fatal: tools retry the connection on demand and report the error.
        log("Failed to initialize Salesforce connection")
    mcp.run()

if __name__ == "__main__":
    main()
