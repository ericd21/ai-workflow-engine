#!/usr/bin/env bash
# Deploy the AI Workflow Engine to Azure Container Apps.
#
# Secret handling: ANTHROPIC_API_KEY / LANGSMITH_API_KEY are read from *your*
# shell environment, written once into Key Vault, and handed to the running
# container only via a Key-Vault-backed secret resolved through a
# user-assigned managed identity. The secret values never appear in this
# script, in an image layer, or in Azure Container Apps' own config — only
# a reference to where the value lives. The app itself is unchanged: it
# still just reads ANTHROPIC_API_KEY with os.getenv(), same as locally.
#
# The image is built by `az acr build` (a cloud build service, ACR Tasks) —
# no local Docker daemon required. Run this from a shell with the `az` CLI
# installed and `az login` already done (e.g. a GitHub Codespace on this
# repo, which provisions the CLI automatically via .devcontainer/).
#
# Usage:
#   ANTHROPIC_API_KEY=sk-... LANGSMITH_API_KEY=ls-... ./scripts/deploy_azure.sh
#
# Re-running is safe: every step below is create-or-update. Names with
# global-uniqueness requirements (the registry and the vault) have defaults
# baked in below — override them via env vars if they collide with someone
# else's resources.

set -euo pipefail

: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY in the environment before running this script}"
: "${LANGSMITH_API_KEY:?Set LANGSMITH_API_KEY in the environment before running this script}"

if ! az account show --output none 2>/dev/null; then
  echo "Not logged in to Azure. Run 'az login' first" >&2
  echo "(on a remote/Codespace terminal with no local browser: 'az login --use-device-code')." >&2
  exit 1
fi

RESOURCE_GROUP="${RESOURCE_GROUP:-ai-workflow-engine-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-acraiwfericd21}"          # alnum only, globally unique
KEY_VAULT_NAME="${KEY_VAULT_NAME:-kv-aiwf-ericd21}"  # <=24 chars, globally unique
IDENTITY_NAME="${IDENTITY_NAME:-ai-workflow-identity}"
ENV_NAME="${ENV_NAME:-ai-workflow-env}"
APP_NAME="${APP_NAME:-ai-workflow-engine}"
IMAGE_NAME="ai-workflow-engine"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

# New/free subscriptions typically start with most resource providers
# unregistered. Register everything this deployment needs up front instead
# of failing partway through for each one (MissingSubscriptionRegistration).
# One-time per subscription — a no-op on every later run.
echo "==> Ensuring required resource providers are registered (first run only, ~1-2 min)"
for ns in Microsoft.ContainerRegistry Microsoft.App Microsoft.OperationalInsights \
          Microsoft.ManagedIdentity Microsoft.KeyVault; do
  state=$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo "NotRegistered")
  if [ "$state" != "Registered" ]; then
    echo "    registering $ns..."
    az provider register --namespace "$ns" --wait
  fi
done

echo "==> Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Container registry: $ACR_NAME"
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --output none

echo "==> Building the image in the cloud (no local Docker needed): ${IMAGE_NAME}:${IMAGE_TAG}"
az acr build --registry "$ACR_NAME" --image "${IMAGE_NAME}:${IMAGE_TAG}" .
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)

echo "==> User-assigned managed identity: $IDENTITY_NAME"
az identity create --resource-group "$RESOURCE_GROUP" --name "$IDENTITY_NAME" --output none
IDENTITY_ID=$(az identity show --resource-group "$RESOURCE_GROUP" --name "$IDENTITY_NAME" --query id -o tsv)
IDENTITY_PRINCIPAL_ID=$(az identity show --resource-group "$RESOURCE_GROUP" --name "$IDENTITY_NAME" --query principalId -o tsv)

echo "==> Granting the identity pull access to the registry (AcrPull)"
ACR_ID=$(az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --query id -o tsv)
az role assignment create \
  --assignee-object-id "$IDENTITY_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "AcrPull" --scope "$ACR_ID" --output none

echo "==> Key Vault: $KEY_VAULT_NAME (RBAC authorization, not legacy access policies)"
az keyvault create \
  --resource-group "$RESOURCE_GROUP" --name "$KEY_VAULT_NAME" --location "$LOCATION" \
  --enable-rbac-authorization true --output none
KEY_VAULT_ID=$(az keyvault show --name "$KEY_VAULT_NAME" --query id -o tsv)

echo "==> Granting the identity read-only secret access (Key Vault Secrets User — least privilege)"
az role assignment create \
  --assignee-object-id "$IDENTITY_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KEY_VAULT_ID" --output none

echo "==> Waiting ~30s for the role assignment to propagate before the app tries to use it"
sleep 30

echo "==> Storing secrets in Key Vault (values are not echoed, not saved to disk)"
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name anthropic-api-key --value "$ANTHROPIC_API_KEY" --output none
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name langsmith-api-key --value "$LANGSMITH_API_KEY" --output none

echo "==> Container Apps environment: $ENV_NAME"
az containerapp env create --resource-group "$RESOURCE_GROUP" --name "$ENV_NAME" --location "$LOCATION" --output none

echo "==> Container app: $APP_NAME"
az containerapp create \
  --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --environment "$ENV_NAME" \
  --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --target-port 8000 --ingress external \
  --min-replicas 0 --max-replicas 2 \
  --secrets \
    "anthropic-api-key=keyvaultref:https://${KEY_VAULT_NAME}.vault.azure.net/secrets/anthropic-api-key,identityref:${IDENTITY_ID}" \
    "langsmith-api-key=keyvaultref:https://${KEY_VAULT_NAME}.vault.azure.net/secrets/langsmith-api-key,identityref:${IDENTITY_ID}" \
  --env-vars \
    "ANTHROPIC_API_KEY=secretref:anthropic-api-key" \
    "LANGSMITH_API_KEY=secretref:langsmith-api-key" \
    "LLM_PROVIDER=anthropic" \
    "LANGSMITH_TRACING=true" \
  --output none

FQDN=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --query properties.configuration.ingress.fqdn -o tsv)

echo
echo "Deployed: https://${FQDN}"
echo "Health check: https://${FQDN}/health"
