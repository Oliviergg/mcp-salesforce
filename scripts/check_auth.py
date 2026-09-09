"""Checks the Salesforce credentials without revealing them.

Prints the auth flow, a masked fingerprint of the client id, and the identity
Salesforce hands back for the connected app's run-as user.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from mcp_salesforce.server import SalesforceClient, resolve_login_url  # noqa: E402


def mask(value):
    if not value:
        return "<not set>"
    if len(value) <= 12:
        return f"<set, {len(value)} chars>"
    return f"{value[:6]}...{value[-4:]} ({len(value)} chars)"


def main():
    client = SalesforceClient()
    print(f"Instance URL   : {resolve_login_url(os.getenv('SALESFORCE_INSTANCE_URL'))}")
    print(f"Client id      : {mask(os.getenv('SALESFORCE_CLIENT_ID'))}")
    print(f"Client secret  : {mask(os.getenv('SALESFORCE_CLIENT_SECRET'))}")

    if not client.connect():
        print(f"\nFAILED: {client.last_error}")
        return 1

    print(f"\nAuth flow      : {client.auth_flow}")
    print(f"Session        : {mask(client.sf.session_id)}")
    print(f"API version    : v{client.sf.sf_version}")

    identity = client.sf.session.get(
        f"{client.sf.base_url.split('/services/')[0]}/services/oauth2/userinfo",
        headers={'Authorization': f'Bearer {client.sf.session_id}'},
    ).json()
    print(f"Run-as user    : {identity.get('preferred_username')}")
    print(f"Organization   : {identity.get('organization_id')}")

    count = client.call(lambda sf: sf.query("SELECT Id FROM User LIMIT 1"))
    print(f"Test query     : ok ({count['totalSize']} row)")
    print("\nOK")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
