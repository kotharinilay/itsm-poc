# Integrations Service (`integrations/`) — ADR-0007

Separate deployable; owns every call to an external system (ServiceNow, Microsoft Graph, OneLogin, Duo, MCP servers), per-organisation connector credentials and egress. Does no reasoning, holds no graph, reaches no model provider.

## Source map (`src/integrations/`)
- `api/` — FastAPI app, `workload/routes.py` (sync path via APIM), middleware (correlation, identity, provenance, problems) — duplicated from RagCore on purpose.
- `catalogue/` (registry, repository) + `domain/catalogue.py` — tool catalogue & connector registry.
- `policy/checks.py` — re-checks policy on the durable record; never trusts the message.
- `execution/` — executor, idempotency, result normalization.
- `connectors/{servicenow,graph,onelogin,duo}/` — adapters (only servicenow, graph have adapters so far); `mcp/client.py`.
- `credentials/resolver.py` — per-org credential resolution (Key Vault).
- `messaging/` — consumer, envelope (jobId only), publisher (result events back to RagCore).
- `persistence/` — jobs, executions, audit (appends to the single audit store; schema/grants are migrations in RagCore).
- `workers/command_consumer.py` — Service Bus async path.
- `scripts/emit_contracts.py` — OpenAPI emission.
- Gates run via `dev.sh python` and CI `.github/workflows/integrations.yml`.
