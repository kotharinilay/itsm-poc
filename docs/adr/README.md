# Architecture Decision Records

Every architectural decision is recorded here in **MADR** structure, numbered sequentially, with a
status field (constitution Principle X). An unrecorded decision is re-litigated; a silent divergence
from `Synthia-Platform-Specification.md` is discovered only when it breaks something that trusted it.

Each record distinguishes three things and never blurs them: **what the source requirements state**,
**what was decided at implementation**, and **what remains unresolved**.

## Records in force

| # | Title | Status | Decides |
|---|---|---|---|
| [0001](./0001-ragcore-owns-orchestration-dotnet-owns-read.md) | RagCore owns orchestration and execution; the .NET modular monolith owns read | **Accepted** | The runtime decomposition. Two deployables, no application dependency, meeting only at PostgreSQL and Service Bus |
| [0002](./0002-approval-api-placement-and-graph-resume.md) | Approval API placement and the graph resume path | **Accepted** | Approval writes go to RagCore; a verdict resumes a suspended graph through outbox → trigger → claim, never through a client |
| [0003](./0003-database-migrations-and-rollback.md) | Database migrations: Alembic, CI-gated execution, and the rollback policy | **Accepted** | Alembic owns every migration; migrations run as a gated job, never at startup; expand/contract rather than rollback |
| [0004](./0004-endpoint-script-integrity-privilege-and-attestation.md) | Endpoint script distribution, privilege level, and result attestation | **Accepted** | Answers specification OQ-03, OQ-04, OQ-05 — fetch per execution with hash verification, no elevation in Alpha, a client result is a claim not proof |
| [0005](./0005-third-party-target-systems.md) | Third-party target systems: OneLogin, Duo and the extensible set | **Accepted** | They are target systems reached as MCP servers, not identity providers; the set is open |

## Open items these records do not close

Recorded so they are met as decisions rather than discovered mid-implementation.

| Item | Where | Met at |
|---|---|---|
| **OQ-08** — reconciliation when a trigger arrives at an unexpected checkpoint position | ADR-0002 §Unresolved | Phase 13 (T117, resume worker) |
| **OQ-01** — second consequential operation in one session | Specification §40; `spec.md` §Dependencies | Stage 14 |
| Script signing for GA; the "destructive" taxonomy | ADR-0004 §Unresolved | Before endpoint execution expands beyond Alpha |

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
