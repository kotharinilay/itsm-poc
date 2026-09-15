# Synthia

Autonomous IT service management agent, operated by Synoptek for multiple customer organisations from
a single deployment.

**This repository currently contains the engineering scaffold — no product use cases.** UC-01 through
UC-12 are placeholders awaiting product definition. Until they exist, every request requiring an action
falls back to manual resolution. That is the designed outcome, not a defect.

## Authoritative documents

Each is authoritative on its own axis. **No document may be reinterpreted to override another.**

| Document | Authoritative on |
|---|---|
| [`Synthia-Platform-Specification.md`](./Synthia-Platform-Specification.md) | **Architecture** — structure, boundaries, trust model, data ownership |
| [`.specify/memory/constitution.md`](./.specify/memory/constitution.md) | **Engineering governance** — how software is built, tested, reviewed, secured |
| [`specs/001-platform-scaffold/plan.md`](./specs/001-platform-scaffold/plan.md) | **Technical realization** |
| [`specs/001-platform-scaffold/tasks.md`](./specs/001-platform-scaffold/tasks.md) | **Executable work** |
| [`docs/adr/`](./docs/adr/) | Recorded architectural decisions |

Where architecture and engineering governance genuinely conflict, **implementation stops** and the
conflict is resolved as an ADR — never settled by whichever document was read first.

## Two deployables, and the rule between them

```text
                    Front Door + WAF  ──▶  APIM  ──┬──▶  RagCore    (Python, writes)
                                                    └──▶  Monolith   (.NET, reads)

    RagCore  ─────────────── PostgreSQL ───────────────  Monolith
                        (versioned vw_*_v1 views)

    RagCore  ─────────────── Service Bus ──────────────  RagCore workers
                         (opaque triggers)
```

**RagCore** (`ragcore/`) owns orchestration, execution and **every state-changing operation**.
**The .NET modular monolith** (`dotnet/`) is **read-only** and exposes no write endpoint, ever.

> **They have no application-level dependency in either direction.** No API call, no library
> reference, no deployment coupling. They meet at exactly two places: PostgreSQL, through versioned
> views RagCore owns, and Service Bus, through triggers that carry only opaque identifiers.

This is [ADR-0001](./docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md), and it is enforced
mechanically: `build/scripts/check-boundaries.sh` fails CI on any cross-tree reference, and
architecture tests assert it from inside each stack. A violation is a build failure, not a review note.

## Layout

```text
apps/web/         One Angular workspace — 3 applications, 4 libraries
apps/desktop/     Electron host. Thin, hardened, decides nothing
dotnet/           Read-only modular monolith — 6 modules, 1 composition root
ragcore/          Orchestration, execution, all writes, all migrations
build/            Dockerfiles, AI Gateway policy, boundary and gate scripts
docs/adr/         Architecture decision records (MADR)
specs/            Specification, plan, tasks, contracts, checklists
```

## Getting started

Requires **.NET 10 SDK**, **Node 20+**, **uv** (which provisions Python 3.12), and **Git**.

```bash
./build/scripts/dev.sh setup     # restore all four toolchains
./build/scripts/dev.sh validate  # run every gate the CI runs
```

On Windows, `pwsh ./build/scripts/dev.ps1 setup` is the equivalent. Run `dev.sh help` for the full
command list. Every command it exposes is the same command CI runs — there is no gate you can only
discover by pushing.

## Validation gates

A change merges only when **all** of these pass, with no new suppressions:

| Gate | Command |
|---|---|
| .NET build + analyzers | `dotnet build dotnet/Synthia.sln -warnaserror` |
| .NET format | `dotnet format dotnet/Synthia.sln --verify-no-changes` |
| .NET tests | `dotnet test dotnet/Synthia.sln` |
| Python lint + format | `uv run ruff check . && uv run ruff format --check .` |
| Python types | `uv run mypy --strict src/` |
| Python tests | `uv run pytest` |
| Web lint + build + test | `npm run lint && npm run build && npm run test` |
| Desktop security suite | `npm run test --workspace apps/desktop` |
| Cross-deployable boundary | `./build/scripts/check-boundaries.sh` |

**No gate is a performance figure.** No release is gated on responsiveness and no merge is blocked by
one (constitution §Non-functional commitments).

## What this scaffold deliberately does not do

- **Resolve any use case.** The governance catalogue holds only inert, labelled reference fixtures,
  excluded from production configuration and never counted as a use case.
- **Execute any script on an endpoint.** The desktop path and its safeguards exist; nothing runs.
- **Reach a real ServiceNow, Graph, OneLogin or Duo instance.** Adapter boundaries exist; no live
  credential does.

If you are looking for where a behaviour lives and cannot find it, check
[`specs/001-platform-scaffold/tasks.md`](./specs/001-platform-scaffold/tasks.md) §Deferred before
assuming it was missed — the omissions are recorded on purpose.
