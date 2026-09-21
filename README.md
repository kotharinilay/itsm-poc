# Synthia

Autonomous IT service management agent, operated by Synoptek for multiple customer organisations from
a single deployment.

**This repository currently contains the engineering scaffold — no product use cases.** UC-01 through
UC-12 are placeholders awaiting product definition. Until they exist, every request requiring an action
falls back to manual resolution. That is the designed outcome, not a defect.

## Authoritative documents

Each is authoritative on its own axis. **No document may be reinterpreted to override another.**

**Architecture — exactly these three, and nothing else:**

| Document | Owns |
|---|---|
| [`docs/architecture/identity-plane-final.md`](./docs/architecture/identity-plane-final.md) | The principal, tenant binding, authority semantics, work-item immutability |
| [`docs/architecture/Synthia-OverallArchitecture-final.md`](./docs/architecture/Synthia-OverallArchitecture-final.md) | Topology, zones, trust boundaries, the stores and their lifecycle |
| [`docs/architecture/RagAgent-Architecture-final.md`](./docs/architecture/RagAgent-Architecture-final.md) | Graph topology and state, node contracts, execution authority, retrieval, release gates |

**Engineering and governance:**

| Source | Authoritative on |
|---|---|
| [`.claude/rules/`](./.claude/rules/) | The engineering baseline and the four change gates — .NET, Python, frontend, testing, security, database, LangGraph, ADR |
| [`CLAUDE.md`](./CLAUDE.md) | The map of the above: which authority answers which question |
| [`.claude/skills/`](./.claude/skills/) | The procedures that apply a gate — `db-change`, `langgraph-change`, `adr-author`, `functional-update`. A procedure, never authority |

**Functional knowledge and history:**

| Source | Records |
|---|---|
| [`docs/functional/implemented.md`](./docs/functional/implemented.md) | What this repository demonstrably does today. It records; it authorizes nothing |
| [`docs/adr/`](./docs/adr/) | Recorded architectural decisions, MADR, sequentially numbered |

Where architecture and engineering governance genuinely conflict, **implementation stops** and the
conflict is resolved as an ADR — never settled by whichever document was read first.

> **Not authority.** `Synthia-Platform-Specification.md` is **history** — not architecture
> authority, not the engineering baseline, and not evidence of implemented behaviour; see
> [`.claude/rules/00-authority.md`](./.claude/rules/00-authority.md) §00.4. It is retained because
> accepted records ADR-0001 to ADR-0008 cite it for their own rationale, and an accepted record is
> never rewritten.

Everything known to be unfinished — deviations, enforcement gaps, defects, conflicts and the
decisions that would close them — is registered in
[`docs/governance/open-items.md`](./docs/governance/open-items.md). The whole governance model on
one page is [`docs/final-repository-governance.md`](./docs/final-repository-governance.md).

## Three deployables, and the rule between them

```text
                    Front Door + WAF  ──▶  APIM  ──┬──▶  RagCore       (Python, writes)
                                                    ├──▶  Integrations  (Python, egress)
                                                    └──▶  Monolith      (.NET, reads)

    RagCore  ─────────────── PostgreSQL ───────────────  Monolith
                        (versioned vw_*_v1 views)

    RagCore  ──▶ Service Bus ──▶  Integrations  ──▶ Service Bus ──▶  RagCore
              (jobId only)                        (result event)

    Integrations  ──▶  ServiceNow · Graph · OneLogin · Duo · MCP servers
```

**Three deployables.** **RagCore** (`ragcore/`) owns orchestration, reasoning, governance and
**every state-changing decision**. **The Integrations Service** (`integrations/`) owns **every call
to an external system** — connectors, credentials and egress. **The .NET modular monolith**
(`dotnet/`) is **read-only** and exposes no write endpoint, ever.

> **No two of them have an application-level dependency in either direction.** No library
> reference, no deployment coupling, no direct network route. RagCore and the monolith meet at
> exactly two places: PostgreSQL, through versioned views RagCore owns, and Service Bus, through
> triggers that carry only opaque identifiers. RagCore reaches Integrations at two more: APIM, as
> its own workload principal, and Service Bus, with a message carrying nothing but a job
> identifier — the authority is read from the durable record, never from the message.

**RagCore holds no connector, no connector credential and no vault role for one.** That is not a
convention: the code is absent, the `mcp` dependency is gone, and the Key Vault role was withdrawn
rather than duplicated — so a direct call fails at authorization even where someone writes one.

This is [ADR-0001](./docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md) and
[ADR-0007](./docs/adr/0007-integration-service-boundary.md), and both are enforced mechanically:
`build/scripts/check-boundaries.sh` fails CI on any cross-tree reference, and architecture tests
assert it from inside each stack. A violation is a build failure, not a review note.

## Layout

```text
apps/web/         One Angular workspace — 3 applications, 4 libraries
apps/desktop/     Electron host. Thin, hardened, decides nothing
dotnet/           Read-only modular monolith — 6 modules, 1 composition root
ragcore/          Orchestration, reasoning, governance, all writes, all migrations
integrations/     Every external connector, credential and egress path
build/            Dockerfiles, AI Gateway policy, boundary and gate scripts
docs/adr/         Architecture decision records (MADR)
docs/functional/  What the repository demonstrably does today
docs/governance/  Open deviations, gaps, defects and decisions
azure-pipelines/  CI/CD definitions
.claude/          Engineering baseline, change gates, procedures and hooks
```

## Getting started

Requires **.NET 10 SDK**, **Node 22.18+**, **uv** (which provisions Python 3.12), **Docker** and
**Git**. Docker is not optional for the gates: the migration and persistence tests start a real
PostgreSQL, and `dev.sh images` builds and runs every container.

```bash
./build/scripts/dev.sh setup     # restore all four toolchains
./build/scripts/dev.sh validate  # every gate CI runs, except the images
./build/scripts/dev.sh images    # build, start and inspect the three images
```

On Windows, run these from **Git Bash**, which is what `dev.ps1` shells out to — if WSL's `bash`
comes first on `PATH`, `dev.ps1` finds that instead and fails. Run `dev.sh help` for the full
command list. Every command it exposes is the same command CI runs — there is no gate you can only
discover by pushing.

## Running it locally

Nothing here reaches Azure. Without a vault the services resolve no secrets, no model is called, and
every action-requiring request escalates — which is the designed outcome, not a broken setup.

```bash
# 1. PostgreSQL. Any throwaway instance; this one is wiped when you remove the container.
docker run -d --name synthia-db -e POSTGRES_PASSWORD=local -e POSTGRES_DB=synthia \
  -p 5432:5432 postgres:17-alpine

export SYNTHIA_DB_DSN=postgresql+asyncpg://postgres:local@localhost:5432/synthia

# 2. Schema. Migrations are a gated job and never run at application startup (ADR-0003), so they
#    are a command you run — as is the checkpointer's own setup, in this order.
cd ragcore
uv run alembic upgrade head
uv run python scripts/provision_checkpoint_schema.py

# 3. RagCore. `create_app` is a factory, which is why --factory is not optional.
uv run uvicorn ragcore.api.app:create_app --factory --port 8000

# 4. The read-only monolith, in another shell.
cd dotnet
ReadDatabase__ConnectionString="Host=localhost;Port=5432;Database=synthia;Username=postgres;Password=local" \
  dotnet run --project src/Synthia.Api

# 5. The Integrations Service, in another shell.
cd integrations
SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN=$SYNTHIA_DB_DSN \
  uv run uvicorn integrations.api.app:create_app --factory --port 8100

# 6. A client surface.
cd apps/web && npx ng serve customer-portal    # or staff-portal, or desktop-renderer
cd apps/desktop && npm run start               # Electron, after `npm run build:renderer`
```

**`ng serve` sends no Content-Security-Policy**, and it cannot: the baseline carries a per-response
nonce (ADR-0009). To run a portal the way production does — the built bundle behind the same server
the container uses — build first, then:

```bash
cd apps/web
npm run build
node scripts/csp-host.mjs customer-portal 4300    # or staff-portal
```

`npm run test:csp` does both and asserts the policy arrives, the nonce is fresh per response, and
the portal renders with no violation.

Each service answers `/health/live` and `/health/ready`; readiness goes unready when PostgreSQL is
unreachable, liveness does not. **The workers are not runnable yet** — all seven `main()` functions
raise by design until their container definitions land.

Every application route requires the gateway-derived identity contract, because no deployable parses
a token (A1 — the identity plane). APIM sets it in a deployment; locally you supply it yourself:

```bash
curl -s localhost:8000/api/customer/v1/sessions -X POST \
  -H 'X-Idp-Tenant-Id: <the organisation entra_tid in tenant_mapping>' \
  -H 'X-Idp-Principal-Id: 33333333-3333-3333-3333-333333333333' \
  -H 'X-Idp-Roles: end_user' \
  -H 'X-Idp-Credential-Class: delegated' \
  -H 'X-Idp-Client-Surface: web'
```

A request with no contract is refused with 401, and one supplying a tenant, role or audience as a
parameter with 400. An organisation must exist in `platform.tenant_mapping` to be admitted, so
insert one before expecting anything but 403.

### Configuration

| Variable | Used by | Notes |
|---|---|---|
| `SYNTHIA_DB_DSN` | RagCore, migrations | The only required RagCore setting. No password in a deployment: PostgreSQL is reached by managed identity |
| `SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN` | Integrations | Required; the service does not start without it |
| `ReadDatabase__ConnectionString` | Monolith | Required; start-up validation names it when absent |
| `SYNTHIA_KEYVAULT_VAULT_URI`, `KeyVault__VaultUri` | RagCore, monolith | Optional locally. Absent means no secret is resolved |
| `SYNTHIA_INTEGRATIONS_GATEWAY_BASE_URL` + `SYNTHIA_INTEGRATIONS_ENTRA_SCOPE` | RagCore | The synchronous route to Integrations, through APIM. Either both or neither |

The full set is `ragcore/src/ragcore/config/settings.py`,
`integrations/src/integrations/config/settings.py` and `dotnet/src/Synthia.Api/Configuration/`; each
is validated at startup, and a missing required value stops the process rather than surfacing later.

### Containers

```bash
./build/scripts/dev.sh images
```

Five images: RagCore, the Integrations Service, the read-only monolith, and one per browser portal.
The portal images are static file servers that set the CSP with a per-response nonce — the policy
cannot be a static header, which is why the portals are container apps rather than a storage account
(ADR-0009). Each portal has its own Front Door endpoint and origin, so the customer and staff
surfaces are separate browser origins.

**A committed Dockerfile does not build, and that is the control.** The runtime base is pinned by
digest and the digest is a placeholder until somebody resolves and reviews one, so a production
build fails until they do. The gate above passes the bare tag as an explicit, CI-only override and
then starts each image, which is how the images are known to work before a digest exists.

**Coding agents.** `.mcp.json` registers two MCP servers, both of them tooling and neither of them
authority. [Serena](https://github.com/oraios/serena) (pinned release, launched through `uv`) gives
semantic code navigation across C#, TypeScript and Python; project settings and the onboarding
memories live in `.serena/` — start from `mem:core`, and put personal overrides in
`.serena/project.local.yml`, which is ignored. The **Figma** server (`https://mcp.figma.com/mcp`)
is design reference for the client surfaces and is not needed for backend work; it authenticates
interactively and no credential is committed. Claude Code asks you to approve a server on first
open — **`/mcp` shows which are actually connected.** `CLAUDE.md` §13 says when to use each.

## Validation gates

A change merges only when **all** of these pass, with no new suppressions:

`dev.sh validate` runs all of them in the pipelines' order; each is also runnable on its own. The working
directory matters — the Python and Node gates run from their own tree, because each is its own
project with its own lockfile.

| Gate | Command | From |
|---|---|---|
| Governance guards | `python3 .claude/hooks/test_guards.py` | root |
| .NET build + analyzers | `dotnet build Synthia.sln -warnaserror` | `dotnet/` |
| .NET format | `dotnet format Synthia.sln --verify-no-changes` | `dotnet/` |
| .NET tests | `dotnet test Synthia.sln` | `dotnet/` |
| Python lint + format | `uv run ruff check . && uv run ruff format --check .` | `ragcore/`, `integrations/` |
| Python types | `uv run mypy` | `ragcore/`, `integrations/` |
| Python tests | `uv run pytest` | `ragcore/`, `integrations/` |
| Web lint + types + build + test | `npx eslint . && npx prettier --check . && npx tsc -b && npm run build && npm test` | `apps/web/` |
| Web accessibility sweep | `npm run test:a11y` | `apps/web/` |
| Desktop types + lint + security suite | `npm run typecheck && npm run lint && npx vitest run` | `apps/desktop/` |
| Desktop security guard proven | `./build/scripts/verify-desktop-security-guard.sh` | root |
| API contracts | `./build/scripts/dev.sh contracts` | root |
| Cross-deployable boundary | `./build/scripts/check-boundaries.sh` | root |
| Edge path | `./build/scripts/check-edge-path.sh` | root |
| Container images | `./build/scripts/dev.sh images` | root |

**No gate is a performance figure.** No release is gated on responsiveness and no merge is blocked by
one. No coverage percentage gates a merge either, deliberately
([`.claude/rules/40-testing.md`](./.claude/rules/40-testing.md) §40.10).

**Where the gates run.** The Azure DevOps definitions are in
[`azure-pipelines/`](./azure-pipelines/). `.github/workflows/**` remains the currently authoritative
execution surface until parity is proven against
[`azure-pipelines/PARITY.md`](./azure-pipelines/PARITY.md), which also states the conditions for
removing it.

## What this scaffold deliberately does not do

- **Resolve any use case.** The governance catalogue holds only inert, labelled reference fixtures,
  excluded from production configuration and never counted as a use case.
- **Execute any script on an endpoint.** The desktop path and its safeguards exist; nothing runs.
- **Reach a real ServiceNow, Graph, OneLogin or Duo instance.** Adapter boundaries exist; no live
  credential does.

If you are looking for where a behaviour lives and cannot find it, check
[`docs/functional/implemented.md`](./docs/functional/implemented.md) before assuming it was missed
— it classifies behaviour as implemented, wired but inert, test-only or not implemented, and the
omissions are recorded on purpose.
