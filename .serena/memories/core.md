# Synthia — core map

Autonomous ITSM agent platform (Synoptek, multi-tenant, single deployment). Repo = **engineering scaffold only**: UC-01..UC-12 are placeholders; manual-resolution fallback is the designed outcome. Never invent product use cases.

## Authoritative docs (each on its own axis; none overrides another)
- **Architecture — exactly three:** `docs/architecture/identity-plane-final.md` (A1),
  `docs/architecture/Synthia-OverallArchitecture-final.md` (A2),
  `docs/architecture/RagAgent-Architecture-final.md` (A3). Nothing else is architecture authority.
- **Engineering baseline + the four change gates:** `.claude/rules/**`, mapped by `CLAUDE.md`.
  Language rules are path-scoped and load only for their own tree.
- `docs/functional/implemented.md` — what the repo demonstrably does today. Records; authorizes nothing. Check here before assuming a behaviour is missing.
- `docs/adr/` — MADR ADRs. Architecture vs governance conflict → stop, write ADR.
- `docs/governance/open-items.md` — every known deviation, enforcement gap, defect and open decision. Records; authorizes nothing.
- `docs/final-repository-governance.md` — the whole authority model on one page.

**NOT authority** (history or tooling): `Synthia-Platform-Specification.md`, `.serena/**` including
this memory, `docs/current-implementation/**`, `docs/governance/**`. Retired governance material
survives only in git history and may not be cited from there either
(`.claude/rules/00-authority.md` §00.4).

## Deployables (no app-level dependency between any two, either direction)
- `ragcore/` — Python. Orchestration, LangGraph, governance, ALL writes, ALL Alembic migrations. See `mem:ragcore/core`.
- `integrations/` — Python. Every external-system call (ServiceNow, Graph, OneLogin, Duo, MCP), connector credentials, egress. See `mem:integrations/core`.
- `dotnet/` — .NET 10 modular monolith, READ-ONLY (no write endpoint, ever). See `mem:dotnet/core`.
- `apps/web/` (Angular workspace) + `apps/desktop/` (Electron host) — clients, never security boundaries. See `mem:web/core`.

## Cross-deployable invariants
- RagCore ↔ monolith meet only at PostgreSQL (versioned `vw_*_v1` views RagCore owns) and Service Bus (opaque-ID triggers).
- RagCore → Integrations only via APIM (sync) or Service Bus carrying only a jobId; authority read from durable record, never the message.
- No shared library between deployables; cross-boundary code duplication is deliberate (`.claude/rules/10-principles.md` P-6) — don't "DRY" it into a common package.
- Enforced by `build/scripts/check-boundaries.sh` (CI) + per-stack architecture tests. Violation = build failure.
- Edge: Front Door + WAF → APIM → services. Model calls only via AI Gateway.
- Tenant isolation at every layer; correlation ID + W3C Trace Context propagate everywhere.

## Other dirs
- `build/` — Dockerfiles (`build/docker`), APIM/infra policy, `build/scripts` (dev + guard scripts), contracts.
- `azure-pipelines/` — the CI/CD definitions, one pipeline per concern; see `azure-pipelines/PARITY.md`.
- `.github/workflows/` — the surface currently executing; retained until Azure DevOps parity is proven.
- `build/contracts/` — the generated OpenAPI contracts, gated by `.github/workflows/contracts.yml`. Contracts are code-first (`.claude/rules/20-dotnet.md` BL-6).
- `docs/governance/` — the open-items register.

Related: `mem:tech_stack`, `mem:conventions`, `mem:suggested_commands`, `mem:task_completion`.
