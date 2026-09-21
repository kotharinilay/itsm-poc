# Architecture Decision Records

Every architectural decision is recorded here in **MADR** structure, numbered sequentially, with a
status field (`.claude/rules/70-adr.md`). An unrecorded decision is re-litigated; a silent
divergence from the three authoritative architecture documents is discovered only when it breaks
something that trusted it.

Each record distinguishes three things and never blurs them: **what the source requirements state**,
**what was decided at implementation**, and **what remains unresolved**.

## Records in force

| # | Title | Status | Decides |
|---|---|---|---|
| [0001](./0001-ragcore-owns-orchestration-dotnet-owns-read.md) | RagCore owns orchestration and execution; the .NET modular monolith owns read | **Accepted**, amended in part by 0007 | The runtime decomposition. RagCore owns orchestration and every platform state change; the monolith is read-only with no application dependency in either direction, meeting only at PostgreSQL and Service Bus. **Its "two deployables" framing and Divergences #1–#2 are narrowed by 0007** |
| [0002](./0002-approval-api-placement-and-graph-resume.md) | Approval API placement and the graph resume path | **Accepted** | Approval writes go to RagCore; a verdict resumes a suspended graph through outbox → trigger → claim, never through a client |
| [0003](./0003-database-migrations-and-rollback.md) | Database migrations: Alembic, CI-gated execution, and the rollback policy | **Accepted**, extended by 0007 | Alembic owns every migration; migrations run as a gated job, never at startup; expand/contract rather than rollback. **0007 adds a second schema owner to the same single project and job** |
| [0004](./0004-endpoint-script-integrity-privilege-and-attestation.md) | Endpoint script distribution, privilege level, and result attestation | **Accepted** | Answers specification OQ-03, OQ-04, OQ-05 — fetch per execution with hash verification, no elevation in Alpha, a client result is a claim not proof |
| [0005](./0005-third-party-target-systems.md) | Third-party target systems: OneLogin, Duo and the extensible set | **Accepted**, relocated by 0007 | They are target systems reached as MCP servers, not identity providers; the set is open. **0007 moves their adapters out of RagCore, so this record's paths are stale** |
| [0006](./0006-desktop-renderer-origin-and-csp-nonce.md) | The desktop renderer origin: a privileged custom scheme, not `file://` | **Accepted** | The renderer is served over `app://renderer` so CSP, IPC sender validation and gateway `Origin` work as written; the remote allow-list stays HTTPS/WSS-only; a per-response nonce keeps `'unsafe-inline'` out of every directive |
| [0007](./0007-integration-service-boundary.md) | The Integrations Service boundary | **Accepted** | Three bounded contexts deploy as one service parallel to RagCore. Partially withdraws ADR-0001's Divergence #1. Connector credentials leave the orchestrator; a durable job record carries the instruction so no authority travels in a message |
| [0008](./0008-defer-certificate-based-gateway-to-backend-provenance.md) | Defer certificate-based gateway-to-backend provenance | **Accepted** | The APIM-to-backend client certificate, the forwarded certificate header, the backend hash allow-list and their middleware, rotation, expiry alerting and guards are **deferred in full, with no replacement**. FR-IDENT-012 is marked DEFERRED rather than silently unmet. Backends remain internal-only; APIM remains the trust boundary |
| [0009](./0009-portal-delivery-one-origin-per-browser-surface.md) | Portal delivery: one public origin per browser surface | **Accepted** | The customer and staff portals each get their own Front Door endpoint, origin group and container app, over Private Link under one shared WAF. A static host cannot deliver the Stage 3 CSP, which needs a per-response nonce. Narrows the edge guard's "exactly one origin" rule to an allow-list, and adds the rule that **only the gateway origin may serve `/api`** |
| [0010](./0010-frontend-engineering-baseline.md) | A migrated TypeScript / Angular / Electron engineering baseline | **Accepted** | Migrates a frontend engineering baseline into `.claude/rules/{22-web-typescript,23-angular,24-electron}.md`, using the retired Spec Kit constitution as **migration input only**. Closes UD-1 / B-4 / OQ-2 and Phase 11 blocker B11-2. Accepted by the repository owner; the record on disk carries `Status: Accepted` and is the status authority — this index only reflects it |
| [0011](./0011-required-test-categories-baseline.md) | Migrate the required-test-category baseline and the per-change test matrix | **Accepted** | Migrates the retired constitution's fifteen required test categories, its twelve-row per-change obligation matrix and its coverage policy into `.claude/rules/40-testing.md`, which states neither today. Closes Phase 11 finding D-11-2. Accepted by the repository owner; migrated into `.claude/rules/40-testing.md` §40.8-§40.10 in Phase 14. |

## Open items these records do not close

Recorded so they are met as decisions rather than discovered mid-implementation.

| Item | Where | Met at |
|---|---|---|
| **OQ-08** — reconciliation when a trigger arrives at an unexpected checkpoint position | ADR-0002 §Unresolved | Phase 13 (T117, resume worker) |
| **OQ-01** — second consequential operation in one session | Specification §40; `spec.md` §Dependencies | Stage 14 |
| **OQ-02 remainder** — separating RagCore's delegated and Workload credential classes. ADR-0007 discharges the connector-credential half | ADR-0007 §Unresolved | GA |
| **OQ-06** — the latency re-baseline, deferred again by ADR-0007's restored gateway hops | ADR-0007 §Unresolved | After the Integrations Service lands |
| Which ServiceNow operations are synchronous; the job-row result columns and their column-scoped `GRANT` | ADR-0007 §Unresolved | Before the Integrations contract is frozen |
| Script signing for GA; the "destructive" taxonomy | ADR-0004 §Unresolved | Before endpoint execution expands beyond Alpha |
| Whether the renderer bundle is served from an ASAR archive once packaging lands | ADR-0006 §Unresolved | Packaging |
| **Portal host names and their CORS/`connect-src` reconciliation** | ADR-0009 §Unresolved | The first deployed environment (T227a) |
| **How gateway-to-backend provenance is proved**, the mechanism having been deferred with no replacement | ADR-0008 §Unresolved | Before the platform carries production customer data |

> ADR-0002's §Unresolved section still lists OQ-03, OQ-04 and OQ-05 as open. **ADR-0004 answers all
> three** and is the later record. Read ADR-0004 as governing.

## Writing a new record

Copy the structure of an existing record. Number it sequentially — a number is never reused, including
for a superseded record. Status is one of `Proposed`, `Accepted`, `Superseded by NNNN`, `Deprecated`.

A record is required whenever a decision:

- diverges from `Synthia-Platform-Specification.md` — name the conflict, the reason, the consequence;
- promotes a bounded context to a separately deployed service (constitution Principle V);
- introduces a provider-neutral abstraction before a second provider exists (Principle VI);
- relaxes a security control the constitution states unconditionally — for example disabling the
  Electron sandbox, which plan Stage 4 makes unconditional.

Update this index in the same change. A record that is not indexed is a record nobody finds.
