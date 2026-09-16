# Azure Deployment Notes

Lessons from the first real run of `scripts/deploy_azure.sh` (2026-09-16). Most of these are
now handled *in the script* (idempotency guards, preflight checks); this doc captures the
operational gotchas that live around running it, not in it.

## Dev environment

- **Keep the devcontainer minimal.** The first `.devcontainer/devcontainer.json` used the
  full `devcontainers/python` image plus the `docker-in-docker` feature and took long enough
  to hit the Codespaces creation timeout, falling back to a recovery container. Neither the
  heavy image nor Docker was actually needed — `deploy_azure.sh` builds via `az acr build`
  (cloud-side), specifically to avoid requiring a local Docker daemon. The fix: a minimal
  base image + the `python` and `azure-cli` features only. If you add a feature later, ask
  whether the script actually needs it before adding it.
- **A Windows `chmod +x` doesn't always survive a commit.** Git for Windows commonly has
  `core.fileMode=false`, so a local `chmod +x` on a script isn't recorded in the commit — it
  lands as `100644` and fails with `Permission denied` on Linux/Codespaces. Fix (and how to
  avoid it next time): `git update-index --chmod=+x <file>`, which sets the mode in the index
  directly regardless of `core.fileMode`, then commit. Verify with
  `git ls-files -s <file>` (`100755` = executable, `100644` = not).

## Secrets

- **Prefer GitHub Codespaces secrets over typing keys in the terminal.** Set them in
  Settings → Codespaces → Secrets *before* creating the Codespace (or restart — not just
  reconnect — an existing one after adding them; they're injected at container start, not
  live-added to a running one).
- **If typing them manually**, use `read -rs VAR_NAME` prompts, not
  `VAR_NAME=value ./script.sh` — the inline form gets written verbatim to shell history.
- **Don't verify with `env | grep KEY_NAME`** — the command itself is history-safe, but the
  *output* prints the raw value to your terminal (scrollback, screenshots, screen shares).
  Check presence without exposing the value instead:
  `[ -n "$VAR_NAME" ] && echo set || echo "NOT set"`.

## Azure specifics

- **New/free subscriptions start with most resource providers unregistered.** Registering
  `Microsoft.ContainerRegistry`, `Microsoft.App`, `Microsoft.OperationalInsights`,
  `Microsoft.ManagedIdentity`, and `Microsoft.KeyVault` up front (now in the script) avoids
  hitting `MissingSubscriptionRegistration` once per namespace instead of all at once.
- **An RBAC-authorized Key Vault (`--enable-rbac-authorization true`) grants *no one* secret
  read/write by default — not even whoever created it.** The identity that will *read*
  secrets at runtime needs `Key Vault Secrets User`; the caller *writing* secrets during
  deployment (you, or whatever principal runs the script) separately needs
  `Key Vault Secrets Officer`. Missing the second one is a `ForbiddenByRbac` on
  `setSecret`, not on anything obviously about the vault's own configuration.
- **Not every `az ... create` is idempotent.** Resource group, ACR, and managed identity
  creation are: re-running with the same name/params is a silent no-op. `az role assignment
  create` and `az keyvault create` are not — both error on "already exists" instead of
  reusing what's there. Any script step that isn't naturally idempotent needs an explicit
  "does it already exist?" check before creating (see `assign_role_if_missing()` and the
  Key Vault / container app checks in `deploy_azure.sh`).
- **Container Apps auto-provisions a Log Analytics workspace** if you don't supply one —
  expect an extra "Generating a Log Analytics workspace..." step and a minute or two of
  extra time on `az containerapp env create`. Normal, not an error.

## Cost / cleanup

- **Azure**: `scripts/teardown_azure.sh` deletes the resource group and purges the
  soft-deleted Key Vault (soft-delete is mandatory and keeps the name reserved for a
  retention period otherwise — purging frees it immediately for reuse).
- **GitHub Codespaces**: stopping a Codespace halts compute billing (and it auto-stops after
  ~30 min idle regardless), but its storage keeps counting against your quota/bill until
  it's **deleted**, not just stopped. These are two separate billing surfaces (GitHub vs.
  Azure) — tearing down one doesn't touch the other.
