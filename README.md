# MCP Server for salesforce

## Features

- Connects to Salesforce using environment variables for credentials.
- Authenticates with the OAuth 2.0 **client credentials flow** (recommended), or with the
  legacy username/password SOAP login.
- Re-authenticates automatically when the Salesforce session expires.
- Provides tools to:
  - Run SOQL queries.
  - Run SOSL searches.
  - Retrieve metadata about Salesforce object fields.
  - Get, create, update, and delete Salesforce records.
  - Execute Salesforce Tooling API requests.
  - Execute Apex REST API requests.
  - Make direct REST API calls to Salesforce.
- Caches object field metadata for performance.
- Handles errors and connection issues gracefully.

## Salesforce setup (client credentials flow)

1. In Setup, create (or edit) a **Connected App** with OAuth enabled.
2. Selected OAuth scopes: at least `Manage user data via APIs (api)`.
3. Check **Enable Client Credentials Flow**.
4. In *Manage* → *Edit Policies*, set the **Run As** user: every API call is made as this
   user, so its profile and permission sets define what the MCP server can see and do.
5. Collect the **Consumer Key** and **Consumer Secret**.

The token endpoint for this flow lives on your **My Domain**: `login.salesforce.com` and
`test.salesforce.com` do not serve the `client_credentials` grant.

## Configuration

```
    {
        "mcpServers": {
            "salesforce": {
                "command": "uvx",
                "args": [
                    "mcp-salesforce"
                ],
                "env": {
                    "SALESFORCE_INSTANCE_URL": "acme",
                    "SALESFORCE_CLIENT_ID": "YOUR_CONNECTED_APP_CONSUMER_KEY",
                    "SALESFORCE_CLIENT_SECRET": "YOUR_CONNECTED_APP_CONSUMER_SECRET"
                }
            }
        }
    }
```

### Environment variables

| Variable | Description |
| --- | --- |
| `SALESFORCE_INSTANCE_URL` | My Domain of the org. Accepts a prefix (`acme`, `acme--uat.sandbox.my`), a full host (`acme.my.salesforce.com`), a full URL, or `login`/`test` (password flow only). |
| `SALESFORCE_CLIENT_ID` | Connected app consumer key (client credentials flow). |
| `SALESFORCE_CLIENT_SECRET` | Connected app consumer secret (client credentials flow). |
| `SALESFORCE_USERNAME` | Username (legacy password flow). |
| `SALESFORCE_PASSWORD` | Password (legacy password flow). |
| `SALESFORCE_SECURITY_TOKEN` | Security token (legacy password flow). |
| `SALESFORCE_AUTH_FLOW` | Optional, forces `client_credentials` or `password`. |
| `SALESFORCE_API_VERSION` | Optional, e.g. `62.0`. Defaults to the simple-salesforce default. |
| `MCP_SALESFORCE_ENV_FILE` | Optional, absolute path of the `.env` file to read. |

Without `SALESFORCE_AUTH_FLOW`, the flow is chosen from what is present: client
credentials when `SALESFORCE_CLIENT_ID` and `SALESFORCE_CLIENT_SECRET` are set, otherwise
the username/password login.

For sandboxes, use the sandbox My Domain, e.g.
`SALESFORCE_INSTANCE_URL=acme--uat.sandbox.my`.

### Storing the credentials

Putting the consumer secret in the MCP client config means it sits in clear text in a
file that is often synced or shared. The alternative is a `.env` file readable only by
you:

```
./scripts/set-credentials.sh
```

It prompts for the My Domain, the consumer key and the consumer secret; the two secrets
are read with a hidden prompt, so they never reach the screen, the shell history or the
process arguments. The file is written with mode `600`.

The server reads `MCP_SALESFORCE_ENV_FILE` if set, otherwise it looks for a `.env` file
from the working directory upwards, then next to the package. Point the MCP client at an
explicit path when installing with `uvx`:

```
    "env": { "MCP_SALESFORCE_ENV_FILE": "/Users/you/.config/mcp-salesforce/.env" }
```

Environment variables always take precedence over the file.

Verify the credentials without printing them:

```
python scripts/check_auth.py
```

It reports the flow used, a masked fingerprint of the key, and the connected app's
run-as user as Salesforce sees it.

### Legacy username/password flow

Still supported, but Salesforce is retiring the SOAP `login()` call and orgs increasingly
block it (MFA requirements, "API access with legacy protocols" disabled). Prefer the
client credentials flow.

```
                "env": {
                    "SALESFORCE_INSTANCE_URL": "login",
                    "SALESFORCE_USERNAME": "YOUR_SALESFORCE_USERNAME",
                    "SALESFORCE_PASSWORD": "YOUR_SALESFORCE_PASSWORD",
                    "SALESFORCE_SECURITY_TOKEN": "YOUR_SALESFORCE_SECURITY_TOKEN"
                }
```

You can also use it with simonw/llm cli utils.
