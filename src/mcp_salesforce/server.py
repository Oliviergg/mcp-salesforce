import asyncio
import json
from typing import Any, Optional, Dict, List
import os
from dotenv import load_dotenv

from simple_salesforce import Salesforce

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("salesforce")

# Load environment variables
load_dotenv()

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
    """Handles Salesforce operations and caching."""
    
    def __init__(self):
        self.sf: Optional[Salesforce] = None
        self.sobjects_cache: dict[str, Any] = {}

    def connect(self) -> bool:
        """Establishes connection to Salesforce using environment variables.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            domain = os.getenv('SALESFORCE_INSTANCE_URL')
            if domain is None:
                domain = 'test'
            elif domain not in ['login', 'test'] and not domain.endswith('.my'):
                domain = f"{domain}.my"
            print(f"Salesforce domain: {domain}")
            self.sf = Salesforce(
                domain=domain,
                username=os.getenv('SALESFORCE_USERNAME'),
                password=os.getenv('SALESFORCE_PASSWORD'),
                security_token=os.getenv('SALESFORCE_SECURITY_TOKEN')
            )
            return True
        except Exception as e:
            print(f"Salesforce connection failed: {str(e)}")
            return False
    
    def get_object_fields(self, object_name: str) -> str:
        """Retrieves field Names, labels and types for a specific Salesforce object.
        if there is a lookup, the type is reference.
        - Type: `reference(18)` to LookupTable via LookupField

        Args:
            object_name (str): The name of the Salesforce object.

        Returns:
            str: a markdown formatted string with the object fields.
        """
        response = self.sf.restful(f'sobjects/{object_name}/describe')
        return format_sobject_metadata_for_llm(response)


@mcp.tool()
async def run_soql_query(query: str) -> str:
    """Executes a SOQL query against Salesforce.
    Args:
        query: The SOQL query to execute
        
    When using this tool, always use a column name in the query. 
    It is important when you aggregate or count. 
    In this case use the Id column. example:  select count(Id) from Account
    """
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        results = sf_client.sf.query_all(query)
        return f"SOQL Query Results:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error executing SOQL query: {str(e)}"

@mcp.tool()
async def run_sosl_search(search: str) -> str:
    """Executes a SOSL search against Salesforce.
    Args:
        search: The SOSL search to execute (e.g., 'FIND {John Smith} IN ALL FIELDS')
    """
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        results = sf_client.sf.search(search)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        sf_object = getattr(sf_client.sf, object_name)
        results = sf_object.get(record_id)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        sf_object = getattr(sf_client.sf, object_name)
        results = sf_object.create(data)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        sf_object = getattr(sf_client.sf, object_name)
        results = sf_object.update(record_id, data)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        sf_object = getattr(sf_client.sf, object_name)
        results = sf_object.delete(record_id)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        results = sf_client.sf.toolingexecute(action, method=method, data=data)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        results = sf_client.sf.apexecute(action, method=method, data=data)
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
    if not sf_client.sf:
        return "Error: Salesforce connection not established."
    
    try:
        results = sf_client.sf.restful(path, method=method, params=params, json=data)
        return f"RESTful API Call Result:\n{json.dumps(results, indent=2)}"
    except Exception as e:
        return f"Error making REST API call: {str(e)}"



def main():
    # Initialize Salesforce client
    global sf_client
    sf_client = SalesforceClient()
    connected = sf_client.connect()
    print(f"Connected: {connected}")
    if not connected:
        print("Failed to initialize Salesforce connection")
    mcp.run()

if __name__ == "__main__":
    main()