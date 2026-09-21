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
- Root `principles.yaml`, `dotnet*.yaml`, `python*.yaml` — the packs `.claude/rules/` was migrated from; the rule files are the operative statement.

**NOT authority** (history): `Synthia-Platform-Specification.md`, `.serena/**` including this memory.
`.specify/**` and `specs/**` were **deleted in Phase 16** and exist only in git history — do not cite them.
The requirement text the retired constitution once held alone was migrated before deletion:
frontend → `.claude/rules/{22-web-typescript,23-angular,24-electron}.md` (`docs/adr/0010`);
testing → `.claude/rules/40-testing.md` §40.8-§40.10 (`docs/adr/0011`);
implementation honesty and reference fixtures → `.claude/rules/10-principles.md` §10.7 H-1/H-2 (`docs/adr/0012`).

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
- `.github/workflows/` — one workflow per tree plus boundaries/contracts/migrations/security/edge.
- `build/contracts/` — the generated OpenAPI contracts, gated by `.github/workflows/contracts.yml`. Contracts are code-first (`.claude/rules/20-dotnet.md` BL-6).
- `.specify/`, `specs/` — **deleted in Phase 16**. The `speckit-*` skills were removed in Phase 12.

Related: `mem:tech_stack`, `mem:conventions`, `mem:suggested_commands`, `mem:task_completion`.
