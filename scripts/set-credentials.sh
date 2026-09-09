#!/usr/bin/env bash
# Writes the Salesforce connected-app credentials to a local .env file.
# Values are read with a hidden prompt: they never appear on screen, in the
# shell history, or in the process arguments.
set -euo pipefail

ENV_FILE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env}"

if [ ! -t 0 ]; then
    echo "This script needs an interactive terminal." >&2
    exit 1
fi

read -r -p "My Domain (e.g. acme or acme--uat.sandbox.my): " SF_DOMAIN
read -r -s -p "Consumer Key: " SF_CLIENT_ID; echo
read -r -s -p "Consumer Secret: " SF_CLIENT_SECRET; echo

if [ -z "$SF_DOMAIN" ] || [ -z "$SF_CLIENT_ID" ] || [ -z "$SF_CLIENT_SECRET" ]; then
    echo "Aborted: empty value." >&2
    exit 1
fi

if [ -e "$ENV_FILE" ]; then
    cp -p "$ENV_FILE" "$ENV_FILE.bak"
    echo "Existing file backed up to $ENV_FILE.bak"
fi

umask 077
cat > "$ENV_FILE" <<ENVEOF
SALESFORCE_INSTANCE_URL=$SF_DOMAIN
SALESFORCE_CLIENT_ID=$SF_CLIENT_ID
SALESFORCE_CLIENT_SECRET=$SF_CLIENT_SECRET
ENVEOF
chmod 600 "$ENV_FILE"

echo "Wrote $ENV_FILE ($(wc -l < "$ENV_FILE" | tr -d ' ') lines, mode 600)."
echo "Check the connection with: python scripts/check_auth.py"
