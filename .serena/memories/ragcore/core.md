# RagCore (`ragcore/`)

Owns orchestration, reasoning, retrieval, governance, approvals, every state-changing decision, and every DB migration. Holds NO connector, connector credential, `mcp` dependency, or Key Vault role for one (guarded by `tests/architecture/test_no_connector_in_ragcore.py`).

## Source map (`src/ragcore/`)
- `domain/` — pure policy/types: authority, decisions, envelopes, governance, principal, roles, tenancy, work, proposal, audit.
- `application/` — use cases (sessions, cases, escalation, cancellation, audit) + `ports.py`.
- `graph/` — LangGraph. `builder.py::build_graph` wires nodes in `graph/nodes/`: intake → converse/clarify → retrieve → ground → guardrail → propose → classify → govern → (await_consent | await_approval → govern) → execute → verify → END, or close. Three durable interrupts (FR-INTR-001). Postgres checkpointer (own schema, excluded from Alembic autogenerate; no second checkpoint store allowed).
- `governance/` — catalogue, conditions, gate, policy; `fixtures.py` = inert reference fixtures only.
- `execution/` — claim, idempotency, executor (dispatches to Integrations; doesn't call external systems).
- `platform_clients/integrations.py` — client to the Integrations Service (via APIM).
- `messaging/` — transactional outbox, publisher, retry, dead-letter, trace context over Service Bus.
- `model/` — AI Gateway egress, local dev seam, content safety (was `integrations/model/`; renamed because AI Gateway is RagCore's own destination).
- `retrieval/` — hybrid search, embedding, rerank, confidence.
- `persistence/` — SQLAlchemy models, repositories, views (published `vw_*_v1`), concurrency, erasure, retention, integration_jobs.
- `api/` — FastAPI: `customer/` (sessions, answers, streaming, feedback, negotiate), `staff/`, `workload/`, `middleware/`, `deps.py`, `openapi.py`.
- `config/` (settings, secrets, composition), `observability/`, `notifications/signalr.py`, `infrastructure/` (azure creds, cache, clock), `egress/`.
- `workers/` (top-level) — outbox_dispatch, resume_worker, integration_result_worker, expiry_sweep, retention_sweep, ingestion_run.
- `migrations/versions/` — Alembic, sequential `NNNN_*.py`; includes Integrations' schema/principal/grants (RagCore owns all migrations).
- `tests/` — unit, integration, isolation, governance, security, messaging, migrations, egress, contracts, architecture, support.
