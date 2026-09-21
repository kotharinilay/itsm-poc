# Synthia — working agreement

Synthia is an autonomous IT service management agent, operated for multiple customer organisations
from a single deployment. This file is the map: it says which authority answers which question and
routes you to the file that owns the answer. **It never states a rule that a rule file owns.**

Read `.claude/rules/00-authority.md` first. It is the authority model in full.

---

## 1. The three questions, and what answers each

```text
What SHOULD this platform be?     ->  the three architecture documents (§2)
How SHOULD code in it be written? ->  .claude/rules/**                 (§3)
What DOES it do today?            ->  implementation evidence, recorded
                                      in docs/functional/implemented.md (§4)
```

These are different questions with different answers and **they are never conflated**. Architecture
describes intent. The functional record describes behaviour. Neither is the other, and neither
licenses the other.

## 2. Architecture authority — exactly three documents

| Ref | Document | Owns |
|---|---|---|
| **A1** | `docs/architecture/identity-plane-final.md` | principal, tenant binding, authority semantics, work-item identity fields and their immutability |
| **A2** | `docs/architecture/Synthia-OverallArchitecture-final.md` | topology, zones, trust boundaries, the stores and their classification, residency and lifecycle |
| **A3** | `docs/architecture/RagAgent-Architecture-final.md` | graph topology and state, node contracts, execution authority, retrieval, the evaluation harness and release gates, ADR-001…ADR-012 inline |

**Nothing else is architecture authority.** Not `docs/architecture/integrations-service-delta.md`
or `docs/architecture/ragcore-langgraph-flow.md`, which sit in the same directory and carry none.
Not `README.md`, `Synthia-Platform-Specification.md`, `.serena/**`,
`docs/current-implementation/**`, `docs/governance/**`, or `docs/adr/**`.

An ADR **records a decision** to change an authority. It never becomes one
(`.claude/rules/70-adr.md` §70.1).

## 3. Engineering baseline — `.claude/rules/**`, and nothing else

| File | Scope |
|---|---|
| `00-authority.md` | repository-wide — authority, precedence, conflicts, deviations |
| `10-principles.md` | repository-wide — P-1…P-32, C-1…C-6, and §10.7 H-1/H-2 |
| `20-dotnet.md` | **.NET / C# only** — `dotnet/**` |
| `21-python.md` | **Python only** — `ragcore/**`, `integrations/**` |
| `22-web-typescript.md` | **both clients** — `apps/**`: shared client rules and TypeScript |
| `23-angular.md` | **Angular only** — `apps/web/**` |
| `24-electron.md` | **Electron only** — `apps/desktop/**` |
| `30-langgraph.md` | the LangGraph change gate |
| `40-testing.md` | repository-wide testing policy |
| `50-database.md` | the database change gate |
| `60-architecture-gates.md` | cross-gate ordering, conformance findings |
| `70-adr.md` | the ADR gate |
| `80-security-ops.md` | repository-wide security and operational policy |
| `90-functional-knowledge.md` | the implemented-truth record |

The five language files carry a `paths:` frontmatter block and **load only when you touch those
paths**. The nine repository-wide files carry none and load every session.

**A rule is never carried to another stack by analogy. A rule you cannot see still applies — open
the file for the stack you are in.**

`.claude/skills/**` holds the four procedures — `db-change`, `langgraph-change`, `adr-author`,
`functional-update`. **A skill is how a rule is applied; it is never authority.**
`.claude/hooks/**` holds the deterministic guards. **Satisfying a hook is not approval.**

## 4. Functional truth

`docs/functional/implemented.md` is the record of what this repository **demonstrably does today**.

```text
Implement  ->  Test  ->  Verify  ->  THEN update implemented.md
```

Only implementation evidence supports a claim there: source, executable configuration, tests,
schema and migrations, generated contracts, registered routes, workers, build and pipeline
definitions. **Architecture documents, ADRs, this file, plans and prompts are never evidence that
something is implemented.** No planned or future behaviour is ever written there as implemented.
The rule is `.claude/rules/90-functional-knowledge.md`; the procedure is
`.claude/skills/functional-update/SKILL.md`.

## 5. Before writing any application code — the conformance gate

```text
1. Read the architecture authority that owns the subject.
2. Read the .claude/rules/ files that govern the paths you will touch.
3. Read docs/functional/implemented.md for what exists today — and nothing more.
4. Read the existing implementation.
5. Compare it against the architecture and the baseline.
```

**If the area you are about to touch already deviates from architecture or from a mandatory rule:
STOP before generating code.** Report the deviation, the rule or architecture section it breaks,
what the code does now, whether the requested work would extend or depend on it, and what human
decision is needed.

Do not invent a workaround, reinterpret the architecture, edit the architecture to match the code,
silently repair the deviation, or build on top of it. **Known deviations stay as they are unless
separately authorized** — they are registered in `docs/governance/open-items.md`.

## 6. Before implementing a change — the four gates

Each gate is defined in exactly one file, and every one has the same shape:

```text
DETECT (before implementation) -> STOP -> DESCRIBE -> human APPROVAL / ACCEPTANCE
                               -> IMPLEMENT -> TEST -> VERIFY
```

| Gate | Fires when | Rule | Skill |
|---|---|---|---|
| **Database** | the change needs a schema or database change | `.claude/rules/50-database.md` | `db-change` |
| **LangGraph** | the change touches nodes, edges, routing, topology, state, interrupts, resume, execution ordering, termination, checkpoint persistence or side-effect boundaries | `.claude/rules/30-langgraph.md` | `langgraph-change` |
| **ADR** | the change alters architecture, identity/authority, or a mandatory engineering rule | `.claude/rules/70-adr.md` | `adr-author` |
| **Functional record** | verified behaviour changed | `.claude/rules/90-functional-knowledge.md` | `functional-update` |

Ordering when more than one fires is `.claude/rules/60-architecture-gates.md` §60.3. **Database
ordering always wins**, and the functional record is always last.

**Detection happens before implementation, not during it.** A gate found halfway through writing
code is a governance failure even when the resulting change is correct: stop there, set aside the
edits that depend on it, say plainly that the ordering was broken, and restart at DETECT.

### The database gate, in one line

Alembic under `ragcore/migrations/` is the single schema mechanism; the .NET side owns no
migrations; migrations run as a gated job before revision activation, **never at application
startup**. Identity-bearing work-item fields are immutable at the **database permission boundary**
(A1 §12.2) — changing that is an ADR, not an approval.

### The LangGraph gate, in one line

**The LLM never owns execution authority.** `.claude/rules/30-langgraph.md` §30.4 lists the
seventeen changes that need an accepted ADR before implementation, and §30.3 the
execution-authority protections that may never be weakened — not by a refactor, a convenience, or
a test fixture.

### The ADR gate, in one line

MADR records in `docs/adr/`, four-digit sequential numbering (**next: 0013**), a status field, and
`Context` / `Decision` / `Consequences`. **Claude writes the record with status `Proposed`. A human
accepts it. Those are two events and the second is not Claude's.**

## 7. Approval and acceptance are never inferred

None of these is approval or acceptance: the task description implying the change; a prior approval
for a different change; the change being obviously needed; an existing precedent in the tree;
silence; an unanswered question; an approved plan that did not enumerate the change; the permission
mode in force; the session running unattended; **a satisfied hook**.

## 8. Testing

`.claude/rules/40-testing.md` owns this. Two things to carry into every change:

- **Never weaken a test to make a change pass** — no deletion, `skip`, `xfail`, loosened assertion,
  narrowed fixture, or disabled job. If a test now fails, either the change is wrong or the test
  encoded an invariant that is deliberately changing, **and the second is a governance decision,
  not an edit** (§40.1).
- **A change owes test categories.** §40.8 lists the fifteen required categories, §40.9 maps a kind
  of change to the categories it owes, and §40.5 states what a principle owes. A security or
  isolation fix owes a **failing-then-passing** test.

No coverage percentage gates a merge, deliberately (§40.10).

## 9. Language governance

Every executable language in this repository has a governing standard. There is no unexplained one.

| Language / stack | Scope | Governing rule | Tooling that enforces it |
|---|---|---|---|
| **C#** | `dotnet/**` | `20-dotnet.md`, `40-testing.md` §40.2 | Roslyn analyzers at `latest-Recommended`, `TreatWarningsAsErrors`, `EnforceCodeStyleInBuild`, `dotnet format`, `.editorconfig`, xUnit, the architecture suites |
| **Python** | `ragcore/**`, `integrations/**` | `21-python.md`, `40-testing.md` §40.3, plus `30-langgraph.md` for graph code and `50-database.md` for migrations | Ruff (`check` and `format`), mypy `--strict`, pytest, `uv` with a committed `uv.lock` |
| **TypeScript** | `apps/**` | `22-web-typescript.md` | `tsc -b` in strict mode, ESLint, Prettier |
| **Angular, HTML, CSS** | `apps/web/**` | `23-angular.md` | ESLint with the Angular and template-accessibility configs, Karma/Jasmine, Playwright for the a11y and CSP sweeps |
| **Electron TypeScript** | `apps/desktop/**` | `24-electron.md` | ESLint `no-restricted-syntax` security selectors, `tsc`, Vitest, and the security-guard verifier that proves the suite fails when a switch is flipped |
| **JavaScript and `.mjs` tooling** | `apps/*/scripts/**`, `apps/*/eslint.config.js` | `22-web-typescript.md` — it is client tooling, governed with the TypeScript it supports | ESLint, Prettier |
| **Shell (bash)** | `build/scripts/**` | `80-security-ops.md` for what the scripts enforce; `10-principles.md` for how they are written | `set -euo pipefail`; each guard script has a `verify-*` counterpart proving it fails on a planted violation |
| **PowerShell** | `build/scripts/dev.ps1` | as for shell; it is a thin shim that delegates to `dev.sh` | reviewed, not linted — it must stay a shim |
| **Python (governance tooling)** | `.claude/hooks/**` | `21-python.md` for style; the hooks are standalone and depend on no project environment | `python3 .claude/hooks/test_guards.py` |
| **SQL and DDL** | `ragcore/migrations/**` | `50-database.md` — the gate, not a style guide | Alembic single-head, upgrade-from-base, models-match-DDL and every-downgrade checks |
| **YAML and JSON configuration** | `build/**`, `azure-pipelines/**`, `.mcp.json`, the `build/policy/*.json` files | `80-security-ops.md` for secrets, least privilege and supply chain; otherwise the rule that owns the subject | schema validation where a schema exists; the policy files are read and asserted by tests in all three stacks |

A new executable language in this repository needs a governing rule **before** it carries logic.
Adding one is an engineering-baseline change under `.claude/rules/70-adr.md` §70.2 B(6).

## 10. Repository layout

```text
apps/web/         One Angular workspace — 3 applications, 4 libraries
apps/desktop/     Electron host. Thin, hardened, decides nothing
dotnet/           Read-only modular monolith — 6 modules, 1 composition root
ragcore/          Orchestration, reasoning, governance, all writes, all migrations
integrations/     Every external connector, credential and egress path
build/            Dockerfiles, gateway policy, boundary and gate scripts
azure-pipelines/  The CI/CD definitions (§12)
docs/             architecture (A1-A3), adr/, functional/, governance/
.claude/          The engineering baseline, the change gates, procedures and hooks
```

**Three deployables, and no application-level dependency between any two of them.** RagCore owns
orchestration and every state change; the Integrations Service owns every call to an external
system; the .NET monolith is read-only and exposes no write endpoint. They meet only at PostgreSQL
through versioned views, at Service Bus carrying opaque identifiers, and at the gateway. This is
ADR-0001 and ADR-0007, and `build/scripts/check-boundaries.sh` fails the build on a violation.

## 11. Commands

```bash
./build/scripts/dev.sh setup      # restore all four toolchains
./build/scripts/dev.sh validate   # every gate CI runs, except the images
./build/scripts/dev.sh images     # build, start and inspect every container image
python3 .claude/hooks/test_guards.py   # the governance guard suite
```

Per stack: `dotnet build Synthia.sln -warnaserror`, `dotnet format --verify-no-changes` and
`dotnet test` from `dotnet/`; `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`
and `uv run pytest -q` from `ragcore/` and from `integrations/`; `npx eslint .`,
`npx prettier --check .`, `npx tsc -b`, `npm run build`, `npm test`, `npm run test:a11y` and
`npm run test:csp` from `apps/web/`; `npm run typecheck`, `npm run lint` and `npx vitest run` from
`apps/desktop/`.

**A change runs the gates its paths touch. A change under `.claude/` runs the governance suite.**
On Windows run these from Git Bash, which is what `dev.ps1` shells out to.

## 12. CI/CD

CI/CD is defined in `azure-pipelines/`, one pipeline per concern, and documented in
`azure-pipelines/README.md`. `.github/workflows/**` remains in place and is the currently
authoritative execution surface until the Azure DevOps pipelines have actually run and gate parity
is proven — the parity matrix and the deletion criteria are in `azure-pipelines/PARITY.md`. **Do
not delete `.github/` before every criterion there is met.**

Neither surface is authority. A pipeline is where a gate **runs**; the rule that requires the gate
is in `.claude/rules/**`, and a passing pipeline is never evidence that a rule is met
(`.claude/rules/00-authority.md` §00.4).

## 13. MCP tooling

MCP servers are **tooling**. They are not authority, they do not override architecture, a rule or
an ADR, and nothing they return is evidence of implemented behaviour. `.mcp.json` declares them;
declaring a server is not the same as having it connected. **Verify with `/mcp` in Claude Code**
before relying on one, and never commit a credential for one.

| Server | What it is for | When to use it |
|---|---|---|
| **Serena** — `.mcp.json`, `.serena/project.yml` | Semantic, repository-aware code navigation across C#, TypeScript and Python, with onboarding memories in `.serena/` | **Prefer it for finding and understanding code** — symbol lookup, references, call sites — over broad text search. Start from `mem:core`. Personal overrides go in `.serena/project.local.yml`, which is ignored |
| **Figma** — `https://mcp.figma.com/mcp` | Reading design files and design-system references when implementing a client surface | Use it for `apps/web/**` and `apps/desktop/**` design work. **It is not required for backend work and is a dependency of no gate.** A design is a reference: a Figma file never overrides `23-angular.md`, `24-electron.md`, the accessibility requirement FE-NG-5, or the CSP rules |

The Serena memories describe the code as somebody wrote it down. They are the same kind of evidence
as a comment, and `docs/functional/implemented.md` remains the functional record.

## 14. Where the open items live

`docs/governance/open-items.md` registers every known deviation, enforcement gap, source defect,
conflict and human decision. It is **not authority**, and an open item is never permission to
extend the thing it records. Read it before assuming something was overlooked.

`docs/final-repository-governance.md` is the one-page statement of this whole model.

## Non-negotiables

- **Never weaken a test** to make a change pass (`40-testing.md` §40.1).
- **Never infer approval or acceptance** (`00-authority.md` §00.10).
- **Record deviations; do not silently repair them, and never rewrite the baseline to match the
  code** (`00-authority.md` §00.7).
- **Never let the LLM take execution authority** (`30-langgraph.md` §30.3).
- **Satisfying a hook is not approval.** H2, H3 and H5 make a gate visible; they judge nothing.
