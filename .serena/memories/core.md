# Synthia — core map

Autonomous ITSM agent platform (Synoptek, multi-tenant, single deployment). Repo = **engineering scaffold only**: UC-01..UC-12 are placeholders; manual-resolution fallback is the designed outcome. Never invent product use cases (constitution IX).

## Authoritative docs (each on its own axis; none overrides another)
- `Synthia-Platform-Specification.md` — architecture (~200KB; grep, don't read whole).
- `.specify/memory/constitution.md` — engineering governance (principles I–X, baselines, gates).
- `specs/001-platform-scaffold/{plan,tasks}.md` — technical realization / executable work. `tasks.md §Deferred` lists intentional omissions — check before assuming something is missing.
- `docs/adr/` — MADR ADRs 0001–0007. Architecture vs governance conflict → stop, write ADR.
- Root `principles.yaml`, `dotnet*.yaml`, `python*.yaml` — normative language rule packs (`core` rules non-negotiable).

## Deployables (no app-level dependency between any two, either direction)
- `ragcore/` — Python. Orchestration, LangGraph, governance, ALL writes, ALL Alembic migrations. See `mem:ragcore/core`.
- `integrations/` — Python. Every external-system call (ServiceNow, Graph, OneLogin, Duo, MCP), connector credentials, egress. See `mem:integrations/core`.
- `dotnet/` — .NET 10 modular monolith, READ-ONLY (no write endpoint, ever). See `mem:dotnet/core`.
- `apps/web/` (Angular workspace) + `apps/desktop/` (Electron host) — clients, never security boundaries. See `mem:web/core`.

## Cross-deployable invariants
- RagCore ↔ monolith meet only at PostgreSQL (versioned `vw_*_v1` views RagCore owns) and Service Bus (opaque-ID triggers).
- RagCore → Integrations only via APIM (sync) or Service Bus carrying only a jobId; authority read from durable record, never the message.
- No shared library between deployables; cross-boundary code duplication is deliberate (constitution VI) — don't "DRY" it into a common package.
- Enforced by `build/scripts/check-boundaries.sh` (CI) + per-stack architecture tests. Violation = build failure.
- Edge: Front Door + WAF → APIM → services. Model calls only via AI Gateway.
- Tenant isolation at every layer; correlation ID + W3C Trace Context propagate everywhere.

## Other dirs
- `build/` — Dockerfiles (`build/docker`), APIM/infra policy, `build/scripts` (dev + guard scripts), contracts.
- `.github/workflows/` — one workflow per tree plus boundaries/contracts/migrations/security/edge.
- `specs/001-platform-scaffold/contracts/` — OpenAPI contracts.
- `.specify/` — spec-kit (speckit-* skills) templates & scripts.

Related: `mem:tech_stack`, `mem:conventions`, `mem:suggested_commands`, `mem:task_completion`.
