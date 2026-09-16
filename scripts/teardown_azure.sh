#!/usr/bin/env bash
# Tear down everything deploy_azure.sh created (stop paying for it between
# demos/interviews). Key Vault has soft-delete on by default, so its name
# stays reserved for a retention period after the resource group is gone —
# this also purges it so the same name can be reused immediately.
#
# Usage: ./scripts/teardown_azure.sh

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-ai-workflow-engine-rg}"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-kv-aiwf-ericd21}"
LOCATION="${LOCATION:-eastus}"

echo "==> Deleting resource group $RESOURCE_GROUP (this deletes everything in it)"
az group delete --name "$RESOURCE_GROUP" --yes --no-wait

echo "==> Waiting for the resource group deletion to finish before purging the vault"
az group wait --name "$RESOURCE_GROUP" --deleted --timeout 600 || true

echo "==> Purging the soft-deleted Key Vault so the name is free for next time"
az keyvault purge --name "$KEY_VAULT_NAME" --location "$LOCATION" 2>/dev/null \
  || echo "    (nothing to purge — it may already be gone, or deletion is still finishing)"

echo "Done."
