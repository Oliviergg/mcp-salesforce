# MCP Server for salesforce

## Features

- Connects to Salesforce using environment variables for credentials.
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

## Configuration
Claude need this type of configuration
```
    {
        "mcpServers": {
            "salesforce": {
                "command": "uvx",
                "args": [
                    "--from",
                    "mcp-salesforce",
                    "salesforce"
                ],
                "env": {
                    "SALESFORCE_INSTANCE_URL": "YOUR DOMAIN"
                    "SALESFORCE_USERNAME": "YOUR_SALESFORCE_USERNAME",
                    "SALESFORCE_PASSWORD": "YOUR_SALESFORCE_PASSWORD",
                    "SALESFORCE_SECURITY_TOKEN": "YOUR_SALESFORCE_SECURITY_TOKEN"
                }
            }
        }
    }
```
