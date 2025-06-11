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
A standard version to use it, is to setup your claude mcp configuration file like this :
```
    {
        "mcpServers": {
            "salesforce": {
                "command": "uvx",
                "args": [
                    "mcp-salesforce",
                ],
                "env": {
                    "SALESFORCE_INSTANCE_URL": "YOUR DOMAIN" (login | test | your custom domain)
                    "SALESFORCE_USERNAME": "YOUR_SALESFORCE_USERNAME",
                    "SALESFORCE_PASSWORD": "YOUR_SALESFORCE_PASSWORD",
                    "SALESFORCE_SECURITY_TOKEN": "YOUR_SALESFORCE_SECURITY_TOKEN"
                }
            }
        }
    }
```

You can also use it with simonw/llm cli utils.