# Phase 2 — Architecture and Engineering Authority Model

**Status:** Design artifact. **Nothing in this phase is implemented.** No application source was
modified, no file was deleted, no `.claude` rule was created, no Spec Kit machinery was touched.

**Purpose:** define the permanent authority model that replaces Spec Kit governance, so that later
phases can construct `.claude/` without guessing which rule belongs where.

**Companion artifact:** [`phase-2-coverage-matrix.md`](./phase-2-coverage-matrix.md) — the complete
128-row engineering-rule coverage matrix (Output 3).

---

## 0. Sources used, and sources deliberately not used

### Authoritative inputs actually read for this phase

| Kind | File | Used for |
|---|---|---|
| Architecture | `docs/architecture/identity-plane-final.md` | Identity/authority ownership map |
| Architecture | `docs/architecture/Synthia-OverallArchitecture-final.md` | Platform/topology ownership map |
| Architecture | `docs/architecture/RagAgent-Architecture-final.md` | LangGraph/retrieval ownership map |
| Engineering | `principles.yaml` | 32 repository-wide principles |
| Engineering | `python.yaml` | Python profile/toolchain (16 items) |
| Engineering | `python_lang.yaml` | 25 Python language rules |
| Engineering | `dotnet.yaml` | .NET profile/toolchain (18 items) |
| Engineering | `dotnet_lang.yaml` | 37 .NET language rules |

### Implementation artifacts read (enforcement evidence only, never as a source of rules)

Read solely to answer *"is this rule already mechanically enforced, and by what?"* — never to decide
what a rule should say:

`dotnet/Directory.Build.props`, `dotnet/Directory.Packages.props`, `dotnet/.editorconfig`,
`ragcore/pyproject.toml`, `integrations/pyproject.toml`, `.github/workflows/*.yml`,
`build/scripts/` (file names), `dotnet/tests/` (project and test-class names), repository directory
layout.

### Excluded — not read, not used

`.specify/**`, `specs/**`, `README.md`, `Synthia-Platform-Specification.md`,
`docs/current-implementation/**`, `docs/adr/**` contents, Serena memories, and all other repository
prose. No statement in this document derives from any of them.

> **Two files in `docs/architecture/` are NOT authoritative.** `integrations-service-delta.md` and
> `ragcore-langgraph-flow.md` sit in the architecture directory but are not on the authoritative list
> of three. They were **not read** and carry **no authority**. Their location is misleading and is
> raised as **OQ-4**.

> **ADRs embedded inside an authoritative architecture document are authoritative.**
> `RagAgent-Architecture-final.md` §4 contains ADR-001…ADR-012 inline. These are part of an
> authoritative document and therefore carry its authority. This is distinct from the *contents* of
> `docs/adr/**`, which remain excluded. The distinction is recorded as **OQ-5**.

---

## 1. Architecture authority map (Output 1)

Three documents. Three disjoint ownership domains. **No fourth document is created, and none of the
three is merged, summarised-with-authority, or subordinated to another.**

### 1.1 Ownership

| # | Document | Owns (authoritative for) | Explicitly does NOT own |
|---|---|---|---|
| A1 | `docs/architecture/identity-plane-final.md` | Human and workload identity; authentication; authorization (customer and staff); tenant binding and tenant lifecycle/offboarding; persona and surface rules; Entra application model; gateway auth and the gateway→service identity contract; service-to-service and on-behalf-of authority; workload execution identity; the real-time (SignalR) authorization boundary; revocation; audit actor model | Azure resource topology, network subnets, service deployment, product screens, RAG graph structure |
| A2 | `docs/architecture/Synthia-OverallArchitecture-final.md` | Platform topology and zones; deployment and network architecture; component inventory; architecture principles P01–P16; multi-tenancy model at platform level; data architecture (stores, classification, residency, lifecycle); integration/adapter architecture; DevOps and delivery; resilience/DR; observability; FinOps; compliance and the traceability matrix | LangGraph node graph, retrieval thresholds, chunking strategy, approval state machine, action schema, tool-binding schema, evaluation metrics (all explicitly deferred to A3); identity/authority rules (deferred to A1) |
| A3 | `docs/architecture/RagAgent-Architecture-final.md` | LangGraph orchestration and graph topology; graph state shape; node contracts; the execution authority boundary as RagCore observes it; retrieval architecture (two indexes, chunking, embedding, hybrid, rerank, confidence/margin/calibration); clarify loop; typed resolution; governance configuration; approval suspend/resume servicing; signed idempotent execution; evaluation harness and release gates; ADR-001…ADR-012 | The principal/tenant-binding/authority rules themselves (it defers to A1 — "this section defines how RagCore *respects* that authority boundary"); platform network, residency and operational controls (deferred to A2) |

### 1.2 Why this is not a judgement call

Each document states its own boundary, and the boundaries interlock rather than overlap:

- **A1 §"Document boundary"** — the Identity Plane defines *who/which principal, which tenant
  context, which persona, which authority*, and explicitly disclaims resource topology, network
  subnets, service deployment, product screens and RAG graph structure.
- **A2 §9** — *"The Overall Architecture intentionally does not define the LangGraph node graph,
  retrieval thresholds, chunking strategy, approval state machine, action schema, tool-binding schema
  or evaluation metrics."*
- **A2 §8.2** — *"Retrieval-specific behavior must not be redefined here."*
- **A3 §6.3** — *"The exact principal, tenant-binding and authority rules are defined in
  `identity-plane.md`; this section defines how RagCore respects that authority boundary."*

So the ownership model is **read off the documents**, not imposed on them.

### 1.3 Resolution rule when a concern touches two documents

1. **Identify the concern's primary domain** using the table in §1.1.
2. **The owning document governs.** A non-owning document's mention of the same concern is context,
   not authority — even when it is more specific or more recent.
3. **Specificity does not confer authority.** A more detailed statement in a non-owning document does
   not override the owner.
4. **If the two documents actually contradict each other inside a single owner's domain**, that is an
   **architecture conflict**: report it, stop, and require an ADR. Never pick a winner silently.

### 1.4 Worked example of the boundary (the highest-traffic case)

A consequential agent action crosses all three domains. Ownership splits cleanly:

| Question | Owner |
|---|---|
| Which nodes/edges run, what state carries `execution_treatment`, how the interrupt suspends and resumes | **A3** |
| Which principal executes, whose tenant it is bound to, what `requested_by_oid` / `on_behalf_of_oid` mean, whether a SignalR message may carry authority | **A1** |
| Which store holds the work item, what residency and classification apply, which adapter reaches ServiceNow | **A2** |

A3 §6.3 states the boundary normatively (*"The LLM never owns execution authority"*, *"No side effect
may occur directly from an agent node"*) and then hands the definition of principal and tenant binding
back to A1. **This is a deferral, not a conflict.**

### 1.5 Candidate conflicts observed — reported, NOT resolved

Per `<architecture-authority>`, these are recorded and left open. None is resolved here.

| ID | Observation | Why it is not resolved here |
|---|---|---|
| **AC-1** | A3 §6.3 and A2 §9.1 both reference the identity document as **`identity-plane.md`**; the authoritative filename is **`identity-plane-final.md`**. A2 §8.2/§9 likewise reference **`RagAgent-Architecture.md`**, not `RagAgent-Architecture-final.md`. | A cross-reference naming mismatch, not a semantic contradiction. It nonetheless means the documents point at filenames that do not exist. Raised as **OQ-4**; needs an editorial decision, not an ADR. |
| **AC-2** | A2 §8.1 places *"graph checkpoints"* in Azure Postgres. A3 §6.2 defines short-term state as *"checkpointer thread state"* without naming the backing store. | Not a contradiction — A2 owns the store, A3 owns the state shape, and they are consistent. Recorded so a later conformance phase confirms the implementation agrees. |
| **AC-3** | A2 §10 carries two unresolved inline **reviewer notes** on the ServiceNow adapter row (the tenant field *"is assumed right now — confirm with business and Snow TAM"*). | An open item inside an authoritative document. It is authoritative *that this is unresolved*. Flagged as **OQ-6**; it is not Phase 2's to close. |
| **AC-4** | A2 has duplicated headings (`### 8.2` twice, `### 11.1` twice, `### 11.2` twice) and A3 jumps from §10 to §12 (no §11). | Structural/editorial defect in an authoritative document. Does not change meaning. Raised as **OQ-4**. |

> **No architecture conflict was resolved in Phase 2.** Where a contradiction is genuine, the gate in
> §6.2 applies: report, stop, require an ADR.

---

## 2. Engineering authority map (Output 2)

### 2.1 The normalized model

The five YAMLs are **not** a flat rule list. They form two tiers crossed with a language axis:

```
                 ┌─────────────────────────────────────────┐
                 │  principles.yaml  (P1..P32)             │
                 │  REPOSITORY-WIDE, language-agnostic     │
                 │  applies to .NET, Python AND TypeScript │
                 └────────────────┬────────────────────────┘
                                  │
             ┌────────────────────┴────────────────────┐
             │                                         │
  ┌──────────▼──────────┐                   ┌──────────▼──────────┐
  │ .NET                │                   │ Python              │
  │  dotnet_lang.yaml   │  language rules   │  python_lang.yaml   │
  │    DN1..DN37        │                   │    PY1..PY25        │
  │  dotnet.yaml        │  profile/toolchain│  python.yaml        │
  │    P-DN-*, toolchain│                   │    P-PY-*, toolchain│
  └─────────────────────┘                   └─────────────────────┘
             │                                         │
    dotnet/src, dotnet/tests          ragcore/**, integrations/**
```

**The two scoping errors this model exists to prevent:**

- A **language rule must never become repository-wide.** `DN8` (ConfigureAwait(false)) is meaningless
  in Python; `PY7` (pathlib) is meaningless in C#. In the matrix, every `dotnet_lang` and
  `python_lang` row is scoped *"NOT repository-wide"* explicitly.
- A **repository-wide principle must never be narrowed to one language.** `P30` (never swallow an
  error) binds to `CA1031` in C# *and* `E722`/`B904` in Python *and* applies to TypeScript where no
  supplied rule exists. In the matrix, every `principles.yaml` row is scoped
  *"Repository-wide (language-agnostic)"* and lists all five component paths.

### 2.2 The nine required categories

| # | Category | Source rules | Destination | Count |
|---|---|---|---|---|
| 1 | Repository-wide engineering principles | `principles.yaml` P1–P32 | `.claude/rules/10-principles.md` | 32 |
| 2 | .NET rules | `dotnet_lang.yaml` DN1–DN37 + `dotnet.yaml` toolchain/strictness/P-DN-1,1b | `.claude/rules/20-dotnet.md` | 37 + 14 |
| 3 | Python rules | `python_lang.yaml` PY1–PY25 + `python.yaml` toolchain/strictness/P-PY-1,3 | `.claude/rules/21-python.md` | 25 + 13 |
| 4 | TypeScript / Angular / Electron | **No language-specific rule was supplied.** Only P1–P32 apply. | `.claude/rules/22-web-typescript.md` | 0 language rules |
| 5 | LangGraph engineering rules | Derived from **A3** (architecture), not from any YAML | `.claude/rules/30-langgraph.md` | see §10 |
| 6 | Testing rules | `P-PY-2`, `P-DN-2`, `P-DN-3` + principles P3/P21/P32 + A3 §10 release gates | `.claude/rules/40-testing.md` | 3 + gate model |
| 7 | Database engineering / change control | Derived from **A1 §12.2** and **A2 §8** | `.claude/rules/50-database.md` | see §9 |
| 8 | Architecture / ADR governance | `P-PY-5`, `P-DN-5`, `P-PY-4`, `P-DN-4` + A3 ADR practice | `.claude/rules/70-adr.md` | 4 |
| 9 | Security and operational rules | `python.yaml#toolchain.security` + the security-classed DN/PY rules (DN24/25/34/35, PY8/10/15/16/17/18/25) + principles P17/P27 | `.claude/rules/80-security-ops.md` | cross-referenced |

### 2.3 Category 4 — the TypeScript gap, stated precisely

`apps/web/` (Angular: design-system, platform-core, customer-features, staff-features,
customer-portal, staff-portal, desktop-renderer) and `apps/desktop/` (Electron) are real components
with real tooling (`eslint`, `prettier`, `tsc -b`, `ng test`, a `test:architecture` script).

**None of the five supplied YAML files contains a single TypeScript, Angular or Electron rule.**

Per `<engineering-authority>` — *"Do not invent standards for technologies for which no authoritative
rule has been supplied"* — Phase 2 therefore:

- **Does** scope all 32 repository-wide principles to `apps/web/**` and `apps/desktop/**`.
- **Does** record the existing TS tooling as observed enforcement, without granting it rule status.
- **Does NOT** author a TypeScript style guide, an Angular convention set or an Electron security
  baseline.

`.claude/rules/22-web-typescript.md` will therefore contain only: the principle scoping, a pointer to
the existing tooling, and an explicit statement that no language-specific baseline has been supplied.
Raised as **OQ-2**.

### 2.4 Language-rule → component binding

| Rule family | Binds to | Does not bind to |
|---|---|---|
| `principles.yaml` P1–P32 | `dotnet/**`, `ragcore/**`, `integrations/**`, `apps/web/**`, `apps/desktop/**` | — (repository-wide) |
| `dotnet_lang.yaml`, `dotnet.yaml` | `dotnet/src/**`, `dotnet/tests/**`, `dotnet/Directory.*.props`, `dotnet/.editorconfig` | ragcore, integrations, apps |
| `python_lang.yaml`, `python.yaml` | `ragcore/{src,workers,tests}/**`, `integrations/{src,workers,tests}/**`, both `pyproject.toml` | dotnet, apps |

---

## 3. Complete coverage matrix (Output 3)

Delivered in full as [`phase-2-coverage-matrix.md`](./phase-2-coverage-matrix.md).

### 3.1 Results

| Status | Count |
|---|---|
| `MIGRATED_AND_MECHANICALLY_ENFORCED` | 101 |
| `MIGRATED_TO_RULE` | 22 |
| `REQUIRES_FUTURE_ENFORCEMENT` | 5 |
| `MIGRATED_TO_SKILL` | 0 |
| `MECHANICALLY_ENFORCED` (gate only, no rule text) | 0 |
| `NOT_APPLICABLE_WITH_REASON` | 0 |
| **Total** | **128** |

| Mechanical coverage today | Rules |
|---|---|
| Fully gated (fails build/CI) | 83 |
| Partially gated | 20 |
| Not gated | 25 |

### 3.2 Declarations required by `<baseline-coverage>`

- **Zero rules silently dropped.** All 128 rows name a destination file.
- **Zero uses of `NOT_APPLICABLE_WITH_REASON`.** No supplied rule was excused.
- **No row is justified by "already understood", "implicit", "covered by architecture" or
  "common practice".** Every row states a concrete destination, a Claude behavior and a path scope.
- **Scope integrity holds both ways** (see §2.1).

### 3.3 The 5 rules that need a gate that does not exist yet

| Rule ID | Statement | Gate to build |
|---|---|---|
| `lang/python#PY4` | Use the logging module; `print` is banned | Add `T20` (flake8-print) to `select[]` in both `pyproject.toml` files |
| `python.yaml#P-PY-4` | Conventional Commits + SemVer | Commit-message lint CI job (repo-wide) |
| `dotnet.yaml#P-DN-4` | Conventional Commits + SemVer | Same job — these two are the same rule in two profiles |
| `python.yaml#P-PY-6` | Diataxis docs, C4 diagrams, quickstart + ADR pointer | No gate proposed; PR review |
| `dotnet.yaml#P-DN-6` | Same | Same |

**These are retained as rules, not dropped.** Each has a home in `.claude/rules/` and a recorded
missing gate. Retiring Spec Kit does not require building these gates first — it requires that each
rule *has a destination*, which it does.

### 3.4 The baseline-rules input gap

`<baseline-coverage>` requires a row for **every** rule in the explicit `<baseline-rules>` block. **That
block was not present in the Phase 2 input.** The matrix covers the five YAMLs completely and the
explicit baseline not at all. This is **OQ-1** and it is **blocking for Phase 2 sign-off** — see §15.

---

## 4. Proposed `.claude` directory structure (Output 4)

```
CLAUDE.md                                  # root: concise, project-wide, ~1 page
.claude/
  settings.json                            # committed; permissions + hook wiring
  settings.local.json                      # existing; developer-local, gitignored
  rules/
    00-authority.md                        # the authority model + precedence order
    10-principles.md                       # P1..P32, repository-wide
    20-dotnet.md                           # DN1..DN37 + dotnet.yaml profile
    21-python.md                           # PY1..PY25 + python.yaml profile
    22-web-typescript.md                   # principle scoping only; NO invented baseline
    30-langgraph.md                        # LangGraph engineering + change gate
    40-testing.md                          # testing governance
    50-database.md                         # DB engineering + change gate
    60-architecture-gates.md               # deviation gate + architecture-change gate
    70-adr.md                              # ADR + coding-baseline-change governance
    80-security-ops.md                     # security + operational rules
    90-functional-knowledge.md             # docs/functional/implemented.md lifecycle
  skills/
    adr-author/SKILL.md                    # write a MADR ADR into docs/adr/
    db-change/SKILL.md                     # the ordered DB-change procedure
    langgraph-change/SKILL.md              # the ordered LangGraph-change procedure
    functional-update/SKILL.md             # update docs/functional/implemented.md
    architecture-conformance/SKILL.md      # produce a deviation report, no fixes
  hooks/
    <scripts>                              # see §8; only deterministic checks

# Path-scoped instructions, co-located with the code they govern
dotnet/CLAUDE.md                           # pointer -> .claude/rules/20-dotnet.md
ragcore/CLAUDE.md                          # pointer -> 21-python.md + 30-langgraph.md
integrations/CLAUDE.md                     # pointer -> 21-python.md
apps/web/CLAUDE.md                         # pointer -> 22-web-typescript.md
apps/desktop/CLAUDE.md                     # pointer -> 22-web-typescript.md

docs/functional/implemented.md             # created in a later phase (does not exist today)
```

### 4.1 Are the listed components required?

| Component | Required? | Why |
|---|---|---|
| `.claude/rules/` | **Yes** | 128 engineering rules cannot live in `CLAUDE.md` without swamping it, and they need per-language scoping. |
| `.claude/skills/` | **Yes** | The DB, LangGraph, ADR and functional-update gates are multi-step *procedures* with a mandatory order. That is exactly what a skill is for. |
| `.claude/settings.json` | **Yes** | Hook wiring must be committed so every contributor and every agent gets the same gates. A gate that lives only in `settings.local.json` is not governance. |
| `.claude/hooks/` | **Yes, but narrow** | Only for checks that are deterministic and reliably detectable (§8). The judgement-bearing gates stay as rules + skills. |
| Root `CLAUDE.md` | **Yes** | Currently absent. It is the entry point that names the authority model and routes to everything else. |
| Path-scoped `CLAUDE.md` files | **Yes** | This is how a language rule stays bound to its language. It is the mechanism that prevents the §2.1 scoping errors at runtime. |

### 4.2 Constraints honoured

- **No architecture document is copied into `.claude`.** The rules *reference*
  `docs/architecture/*-final.md` by path; they never restate a rule from them.
- **No YAML file is pasted into `CLAUDE.md`.** Rules are re-homed into `.claude/rules/`, not inlined.
- **No new master architecture document is created.**
- **`.claude/rules/00-authority.md` is a navigation aid.** It names which of the three documents owns
  which domain and points at them. It introduces no rule, reinterprets nothing, and overrides nothing.

---

## 5. Responsibility definitions (Outputs 5, 6, 7)

### 5.1 `CLAUDE.md` (root) — Output 5

**Is responsible for:** naming the three architecture documents and their owned domains (one line
each); stating the precedence order; listing the component→language map; naming the six gates and
where each is defined; routing to `.claude/rules/`.

**Is NOT responsible for:** any architecture content; any of the 128 engineering rules; any YAML
content; any language-specific guidance; any procedure.

**Size budget:** roughly one page. If it grows past that, content belongs in `.claude/rules/`.

**Precedence order it must state:**

```
1. The three architecture documents   (within each one's owned domain)
2. .claude/rules/                     (engineering baseline)
3. Mechanical gates                   (build, analyzers, CI)
4. Existing implementation            (evidence of what IS, never authority for what SHOULD BE)
```

Rule 4 is the load-bearing one: it encodes `<important-boundary>` — an observed deviation is never
permission to reinterpret the baseline.

### 5.2 `.claude/rules/` — Output 6

**Is responsible for:** holding the re-homed engineering baseline, one file per category from §2.2;
stating each rule with its source ID (`principles#P5`, `lang/dotnet#DN9`) so traceability back to the
retired YAML survives; stating the expected Claude behavior per rule; naming the gate that catches
violations, where one exists; holding the six gate definitions (§6, §9–§13).

**Is NOT responsible for:** restating architecture; duplicating architecture documents; holding
functional requirements; holding procedures (those are skills).

**Rules on rule files:**

- Every rule keeps its original ID. A reader must be able to trace `.claude/rules/20-dotnet.md` →
  `lang/dotnet#DN9` → the retired `dotnet_lang.yaml` entry.
- A rule that is mechanically enforced still gets rule text, and the text names the gate. Rule text
  tells Claude what to *write*; the gate catches what slips. Both are needed — this is why 101 of 128
  rows are `MIGRATED_AND_MECHANICALLY_ENFORCED` rather than `MECHANICALLY_ENFORCED`.
- Rule files are **path-scoped via the component `CLAUDE.md` pointers**, never by hoping Claude infers
  the language.

### 5.3 `.claude/skills/` — Output 7

**Is responsible for:** repeatable multi-step procedures where the *order* is the governance.

| Skill | Invoked when | Enforces |
|---|---|---|
| `db-change` | a change needs a schema change | the mandatory ordering in §9 |
| `langgraph-change` | a change touches the graph | the mandatory ordering in §10 |
| `adr-author` | an architecture or baseline change is required | ADR format + placement (§11) |
| `functional-update` | verified behavior has changed | `docs/functional/implemented.md` lifecycle (§13) |
| `architecture-conformance` | code deviates from architecture | produce a **report only**, never a fix (§6.1) |

**Is NOT responsible for:** holding rules (those are `.claude/rules/`); making decisions a human must
make; performing remediation that was not explicitly requested.

---

## 6. Architecture gates (part of Output 8; `<required-governance>` 1, 2 and 3)

Defined in `.claude/rules/60-architecture-gates.md`.

### 6.1 Architecture deviation gate

**Trigger:** existing code or project structure does not match the owning architecture document.

**Required behavior:**

1. Report the deviation: what the architecture says, which document and section owns it, what the code
   does, and where.
2. **Do not silently correct it.**
3. **Do not generate corrective code** unless the user explicitly requests remediation.
4. Continue the originally requested work where it does not depend on the deviation.

**Rationale (`<important-boundary>`):** an observed deviation is evidence for a future conformance
audit, not permission to reinterpret the baseline or to rewrite the code.

**Skill:** `architecture-conformance` — produces a report, never a fix.

### 6.2 Architecture-change gate

**Trigger:** the requested feature cannot be implemented without changing architecture — a new
component or zone, a changed trust or tenant boundary, a changed identity/authority rule, a changed
platform topology, a new store, a changed ownership boundary between A1/A2/A3, or a genuine
contradiction between two architecture documents.

**Required behavior:**

1. Report the architecture change the feature requires, naming the owning document and section.
2. **Stop implementation.**
3. **Require an ADR before any architecture-changing implementation begins.**

**Non-negotiable:** the ADR comes *before* the code, not alongside it and not after it.

### 6.3 Coding-baseline change gate

**Trigger:** the requested implementation cannot be done without changing an engineering rule —
relaxing an analyzer severity, adding to ruff `ignore` or `per-file-ignores`, adding a blanket
`# noqa`, setting `TreatWarningsAsErrors=false` on a project, overriding `Nullable`, adding a
`#pragma warning disable` without justification, or contradicting any of the 128 matrix rows.

**Required behavior:**

1. Report which rule (by its source ID) the implementation would require changing.
2. **Stop implementation.**
3. **Require an ADR before implementing the changed approach.**

**This gate is what makes `<important-boundary>` operational.** The baseline is not bent to fit the
implementation; the implementation is changed, or an ADR changes the baseline deliberately.

---

## 7. Hook / enforcement candidate list (Output 8)

**Selection rule:** a hook is proposed **only** where the check is deterministic and reliably
detectable from a diff or a command. Judgement-bearing gates stay as rules and skills — an unreliable
hook is worse than no hook, because it trains people to bypass it.

### 7.1 Already mechanically enforced — no new hook needed

These need **no hook**; they already fail the build or CI. The `.claude` rule text points at them.

| Mechanism | Covers |
|---|---|
| `dotnet/Directory.Build.props` — `Nullable=enable`, `TreatWarningsAsErrors=true`, `CodeAnalysisTreatWarningsAsErrors=true`, `EnableNETAnalyzers=true`, `AnalysisLevel=latest-Recommended`, `EnforceCodeStyleInBuild=true`, `Deterministic=true`, `ManagePackageVersionsCentrally=true`, `net10.0` | DN6, DN7, DN23, most CA-backed DN rules, P-DN-S1…S5, all `dotnet.yaml` toolchain rows |
| `dotnet/.editorconfig` — CA1031, CA1062, CA1707, CA1848, CA1849, CA2007, CA2016, IDE0055, IDE1006 at `severity=error` | DN2, DN3, DN4, DN8, DN9, DN10, DN16, DN28, DN29, DN31, P30, P11 |
| `ragcore/` + `integrations/pyproject.toml` — ruff `select=[E,F,B,I,UP,S,PTH,SIM,ASYNC,DTZ,N]`, `ignore=[]`, mypy `strict=true` | PY1–PY3, PY5–PY25, P-PY-S1/S2, P-PY-1/3, all `python.yaml` toolchain rows |
| `.github/workflows/dotnet.yml` — `build -warnaserror`, `format --verify-no-changes`, `test` | DN7, DN29, P-DN-1b |
| `.github/workflows/ragcore.yml`, `integrations.yml` — `ruff check`, `ruff format --check`, `mypy`, `pytest` as failing steps | PY22, P-PY-S3 |
| `.github/workflows/boundaries.yml` + `build/scripts/check-boundaries.sh`, `verify-architecture-guards.sh`, `verify-boundary-guard.sh` | P5, P13, P24 |
| `dotnet/tests/Synthia.ArchitectureTests` (ModuleIsolationTests, BoundaryOwnershipTests, CompositionRootTests, ServiceResolutionTests, BannedApiTests, NoWriteEndpointTests, IdentityDisciplineTests, AzureIdentityTests, EdgeTrustPolicyTests, NoRagCoreDependencyTests, NoMigrationTests, DataAccessDisciplineTests) | P5, P13, P17, P18, P19, P24, P26, P28, DN3, DN14, DN34 |
| `Synthia.AuthorizationTests`, `Synthia.TenantIsolationTests`, `Synthia.ContractTests` | P17, P32, P3, A1 tenant-binding rules |
| `.github/workflows/security.yml` — gitleaks, `dotnet list package --vulnerable`, `npm audit` | P27, PY15 |
| `.github/workflows/migrations.yml` — single head, upgrade/downgrade, integration tests | DB gate (§9) |

### 7.2 New hook candidates — recommended

| # | Hook | Trigger | Deterministic? | Covers |
|---|---|---|---|---|
| **H1** | **Baseline-relaxation guard** | diff adds to ruff `ignore` / `per-file-ignores`; adds a bare `# noqa` with no code+reason; lowers an `.editorconfig` severity; sets `TreatWarningsAsErrors=false`; overrides `Nullable`/`AnalysisLevel`/`EnforceCodeStyleInBuild` in a `.csproj`; adds `#pragma warning disable` without justification | **Yes** — pure text diff | §6.3 gate, P-PY-S3, P-DN-3, DN21 |
| **H2** | **Migration-without-approval guard** | diff touches `ragcore/migrations/**` or `alembic.ini` | **Yes** — path match | §9 DB gate |
| **H3** | **LangGraph-change guard** | diff touches graph/state/node modules under `ragcore/src/**` | **Yes** — path match | §10 LangGraph gate |
| **H4** | **Test-weakening guard** | diff deletes a test file, adds `@pytest.mark.skip`/`xfail`, adds `[Fact(Skip=...)]`, removes `[Fact]`/`[Theory]`, or reduces assertions in an architecture/security/isolation test | **Yes** — diff pattern | §12 testing gate |
| **H5** | **ADR-numbering check** | diff adds a file to `docs/adr/` | **Yes** — filename + status-field parse | P-PY-5, P-DN-5 |
| **H6** | **Commit-message lint** (Conventional Commits) | commit | **Yes** — regex | P-PY-4, P-DN-4 — the 2 open rules from §3.3 |
| **H7** | **`print()` ban** | Python diff adds `print(` outside `scripts/` | **Yes** — but better solved by adding ruff `T20` | PY4 |

### 7.3 Explicitly rejected as hooks

| Candidate | Why rejected |
|---|---|
| "Does this change require an ADR?" | Requires judgement. Stays a rule + skill. |
| "Is this module single-responsibility?" (P1) | Metrics are a proxy, not the rule. A false positive here teaches bypass. |
| "Does the code match the architecture?" | Not reliably detectable from a diff. Stays the §6.1 rule. |
| "Is `docs/functional/implemented.md` accurate?" | Requires reading behavior. A hook can only check *staleness*, not correctness. |

**H7 note:** prefer adding `T20` to `select[]` over a hook. A ruff code is a real gate; a hook is a
second-best imitation of one.

---

## 8. Reserved

*(Section intentionally left as a placeholder so §9–§13 keep the numbering used by the
`<required-governance>` items 4–7.)*

---

## 9. Database-change governance (Output 9; `<required-governance>` 4)

Defined in `.claude/rules/50-database.md`; procedure in `.claude/skills/db-change/`.

### 9.1 Architectural grounding

| Fact | Owner |
|---|---|
| Azure Postgres holds tenant mapping, chat sessions, work items, approvals and consent, governance and script config, graph checkpoints, audit log | **A2** §8.1 |
| The work item is the authoritative record of tenant, requester, action, target and approval state — and those fields are immutable | **A1** §4.5, **A3** §6.2 |
| `tenant_id`, `requested_by_oid`, `requester_role`, requested action, target, approval requirement, `approved_by_oid`, `approved_at` are **conceptually immutable after creation** | **A1** §12.2 |
| That immutability **must be enforced at the database permission boundary, not only in application code** | **A1** §12.2 |
| Workload may update only execution-owned fields: `status`, lease/execution state, `outcome`, `executed_by`, execution mechanism metadata, execution timestamps | **A1** §12.2 |

This is why the DB gate is ordered *before* application code: in this architecture the database is
part of the **authorization boundary**, not merely a persistence detail. A schema change can weaken a
security invariant.

### 9.2 The mandatory ordering

```
  1. DETECT   — identify the schema change BEFORE any application-code correction
  2. STOP     — halt application implementation
  3. DESCRIBE — affected tables/columns/constraints/indexes; the migration;
                data impact; backfill; downgrade path; which identity-bearing
                fields are touched and whether DB-level permissions change
  4. APPROVE  — explicit human approval. Not inferable, not assumed.
  5. IMPLEMENT + VALIDATE the DB change FIRST
  6. ONLY THEN continue application implementation
```

**Step 1 is the one that is usually got wrong.** The rule is explicit: the DB change is identified
*before* any application-code correction, not discovered partway through one.

### 9.3 Mandatory content of the step-3 description

- Tables, columns, constraints, indexes added/changed/removed
- The Alembic revision, and that `ragcore/migrations/` has a **single head**
- Data impact: existing rows, backfill, nullability transitions
- **Downgrade path** — and if there is none, that stated explicitly
- Whether any **identity-bearing field** from A1 §12.2 is touched
- Whether **database-level permissions** change (an A1 §12.2 boundary change → also §6.2)
- Whether graph checkpoint tables are affected (A2 §8.1 → also §10)

### 9.4 Existing mechanical support

`.github/workflows/migrations.yml` already enforces single-head, upgrade, downgrade and runs
integration tests. `dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs` already asserts the
.NET side owns no migrations. **H2** adds the approval gate these do not cover.

### 9.5 Escalation

A DB change that alters an identity-bearing field's immutability, or the DB permission model, is
**also** an architecture change under A1 §12.2 → the §6.2 gate fires and an **ADR is required**.

---

## 10. LangGraph-change governance (Output 10; `<required-governance>` 5)

Defined in `.claude/rules/30-langgraph.md`; procedure in `.claude/skills/langgraph-change/`.

### 10.1 Architectural grounding

**A3 owns the graph.** A3 §6.3 states the normative boundary:

- *"The LLM never owns execution authority."* It cannot choose or change the authoritative tenant,
  requester, target, approval state, credential profile or execution identity.
- *"No side effect may occur directly from an agent node."* Only the governed execution path may
  perform a consequential operation.
- Before execution the Workload must **re-read the durable work item** and verify tenant, action,
  target, approval and execution-validity state.
- The Workload **must not** accept authority-bearing values from trigger payloads, chat text,
  retrieved documents, SignalR messages or model output.

A graph change can breach any of these silently. That is why the gate exists.

### 10.2 What counts as a LangGraph change

Any change to: **nodes**, **edges/routing**, **state shape**, **interrupts**, **resume behavior**,
**execution ordering**, or **termination behavior**. Concretely, using A3 §6.2's state vocabulary:

| Area | Change that trips the gate |
|---|---|
| Identity & config | adding/changing `tid`, `user_id`, `request_id`, `work_item_id`, `case_ref`, `config` — these are *copies of* trusted context, never the source |
| Clarify loop | `clarify_iterations` bound, `understanding_confidence` / `grounding_confidence` / `score_margin` thresholds, `ambiguity_type`, `pending_question` |
| Long-term working set | `user_profile`, `recalled_incidents` |
| Retrieval & resolution | `probe_candidates`, `resolution_type` {`ACTION`,`SOP`,`NONE`}, `resolution_ref`, `match_confidence`, `sop_document` |
| **Action governance** | `action_definition`, `action_params`, `params_status`, `tool_binding`, **`execution_treatment` {AUTO, END_USER_APPROVAL, STAFF_APPROVAL, NOT_ALLOWED}**, `approval_request_id`, `approval`, `consent`, `action_result` |
| Outcome | `outcome` {answered_sop, resolved_action, escalated, denied}, `escalation_reason` |
| Interrupts | the two interrupts and their transports; suspend/resume; live vs non-live at verdict arrival; correlation |
| Termination | SOP branch terminality (ADR-004); the no-timeout human-only lifecycle (A3 §8.5) |

### 10.3 The mandatory ordering

```
  1. DETECT   — identify the workflow change BEFORE implementation
  2. STOP     — halt implementation
  3. DESCRIBE — affected nodes, edges, state fields, interrupts, resume,
                routing, execution ordering, termination (as applicable)
  4. APPROVE  — explicit approval
  5. ADR      — REQUIRED IF the change alters architecture or an architectural rule
  6. ONLY THEN implement
```

### 10.4 Changes that always require an ADR, not merely approval

A change is architecture-altering — step 5 is mandatory — when it would:

- move an execution decision toward the LLM, contradicting *"the LLM never owns execution authority"*;
- introduce a side effect in an agent node (A3 §6.3);
- change `execution_treatment` semantics or which operations are `AUTO` (ADR-005, A2 §10);
- change the approval model: suspend/resume, verdict source, binding, first-valid-verdict-wins, or the
  no-timeout lifecycle (ADR-010, A3 §8);
- change the signed/idempotent execution keyed on `request_id` (ADR-011);
- change typed resolution or SOP terminality (ADR-004);
- change the two-index model or field-scoped embedding (ADR-003, A3 §9.1/9.2);
- change memory separation (ADR-008) or per-tenant tool injection (ADR-009);
- weaken the mandatory tenant (`tid`) filter (A3 §9.6, A1 tenant-binding monotonicity);
- change release-gate thresholds (ADR-012, A3 §10.3).

### 10.5 Interaction with the DB gate

Graph checkpoints live in Azure Postgres (A2 §8.1). A state-shape change that alters checkpoint
persistence fires **both** §10 and §9 — and §9's ordering wins: **the DB change is identified,
approved, implemented and validated before the graph code changes.**

---

## 11. ADR / change governance (Output 11)

Defined in `.claude/rules/70-adr.md`; procedure in `.claude/skills/adr-author/`.

### 11.1 Format and placement

Per `python.yaml#P-PY-5` and `dotnet.yaml#P-DN-5` (identical rules in two profiles):

- **MADR** format
- in **`docs/adr/`**
- **sequential numbering** (current: `0001`…`0009`)
- a **status field** on every ADR

### 11.2 When an ADR is mandatory

| Trigger | Source |
|---|---|
| A feature cannot be implemented without an architecture change | §6.2 |
| An implementation requires changing a coding/engineering rule | §6.3 |
| A LangGraph change alters architecture or an architectural rule | §10.4 |
| A DB change alters identity-bearing field immutability or the DB permission model | §9.5 |
| Two architecture documents genuinely contradict each other | §1.3(4) |

### 11.3 Ordering

**The ADR precedes the implementation.** Not concurrent. Not retrospective. An implementation that
requires an ADR stops until the ADR exists and is accepted.

### 11.4 Existing ADRs

`docs/adr/0001`…`0009` are **preserved as historical decision records**. Per
`<repository_document_policy>`, their *contents* are not a source for reconstructing the new
architecture or engineering baseline. New ADRs continue the same sequence from `0010`.

### 11.5 Commit/versioning governance

`P-PY-4` / `P-DN-4` (Conventional Commits + SemVer) are re-homed here as the single repo-wide rule
they actually are, rather than duplicated per language. **Currently ungated** — see H6 and §3.3.

---

## 12. Testing governance (Output 12; `<required-governance>` 6)

Defined in `.claude/rules/40-testing.md`.

### 12.1 Testing is a first-class governance concern

Testing is not a by-product of implementation here. The repository already treats it structurally: 11
.NET test projects including dedicated `ArchitectureTests`, `AuthorizationTests`, `TenantIsolationTests`
and `ContractTests`; and `ragcore/pyproject.toml` declares governance-bearing pytest markers —
`isolation`, `governance`, `approval`, `idempotency`, `concurrency`, `security`, `integration`, `e2e`
— each with a stated proof obligation (e.g. *"isolation: proves no path returns another
organisation's data"*).

### 12.2 The six obligations on every code change

1. **Identify applicable tests** before changing code.
2. **Preserve existing applicable tests.**
3. **Create or update tests for changed or new behavior**, where the behavior is testable.
4. **Preserve architecture, security and boundary tests** — specifically `Synthia.ArchitectureTests`,
   `Synthia.AuthorizationTests`, `Synthia.TenantIsolationTests`, `Synthia.ContractTests`, and any
   Python test carrying an `isolation`, `governance`, `approval`, `idempotency`, `concurrency` or
   `security` marker.
5. **Never weaken, delete or skip a test merely to make an implementation pass.** If a test now fails,
   either the implementation is wrong, or the test encodes a rule that an ADR must change first
   (§6.3). Those are the only two options.
6. **Never relax test-project strictness.** Per `dotnet.yaml#P-DN-3`, test projects inherit `src`
   strictness with no relaxed ruleset. Per `ragcore/pyproject.toml`, `tests/**` is exempted from
   `S101` only — that is the mechanism implementing "assert is allowed in tests", not a general
   relaxation.

### 12.3 Re-homed testing rules

| Rule | From | Now in |
|---|---|---|
| `python.yaml#P-PY-2` — tests/ package, pytest, `test_*.py`, descriptive names | python profile | `40-testing.md` |
| `dotnet.yaml#P-DN-2` — tests/ parallel to src/, `<Project>.Tests`, `Method_State_Expected` | dotnet profile | `40-testing.md` |
| `dotnet.yaml#P-DN-3` — test projects inherit src strictness | dotnet profile | `40-testing.md` |
| `principles#P3` (substitutability), `#P21` (idempotency), `#P32` (contracts) | principles | cross-referenced from `10-principles.md` |

### 12.4 Release gates

A3 §10.3 defines evaluation release gates for the agent (ADR-012: *evaluation harness as a release
gate*). These are **A3's to define, not this document's**. `40-testing.md` points at A3 §10; it does
not restate thresholds, since restating them would duplicate an architecture rule with altered
meaning.

### 12.5 Mechanical support

Existing: `dotnet test` in `dotnet.yml`; `pytest` in `ragcore.yml`/`integrations.yml`;
`pytest -m integration` and `-m "not integration"` in `migrations.yml`; `npm run test:unit` and
`test:architecture` in `apps/web`. Proposed: **H4** test-weakening guard.

---

## 13. Functional knowledge governance (Output 13; `<required-governance>` 7)

Defined in `.claude/rules/90-functional-knowledge.md`; procedure in
`.claude/skills/functional-update/`.

### 13.1 The canonical target

**`docs/functional/implemented.md`** — the single canonical record of implemented functional
knowledge.

**This file does not exist today.** `docs/functional/` is not present in the repository. Creating and
populating it is Phase 6 work (`<migration_order>` step 6), and it is a hard prerequisite for Spec Kit
retirement (§14).

### 13.2 The lifecycle

```
  behavior change implemented
          ↓
  behavior change VERIFIED (tests pass, gate green)
          ↓
  update docs/functional/implemented.md
          ↓
  describe ONLY behavior that now exists
```

**The update happens after verification, not after implementation.** Unverified behavior is not
implemented behavior.

### 13.3 Hard constraints

- **Only behavior demonstrated by the current implementation.** It is not a requirements document.
- **No planned functionality.** No roadmap, no "will", no "should".
- **Architecture and requirement documents are not functional evidence.** Per `<implementation_truth>`,
  functional truth comes only from: source code; automated tests; database schema and migrations; API
  implementations and generated/runtime contracts; executable configuration; the LangGraph
  graph/state/workflow implementation; build, CI and validation scripts; and dependency manifests and
  lock files where needed to establish actual behavior.
- **No repository prose document may be used as evidence of implemented functionality** — this
  restriction is stricter than the general document policy and explicitly includes
  `docs/current-implementation/**` and `Synthia-Platform-Specification.md`.

### 13.4 Relationship to the architecture documents

The three architecture documents describe what the system **should** be. `implemented.md` describes
what it **demonstrably is**. Where they disagree, that is a **conformance finding** for the §6.1
deviation gate — it is not a licence to change either one.

---

## 14. Spec Kit retirement prerequisites (Output 14)

### 14.1 The ordering rule

Per `<migration_order>`: **never remove `.specify/**` or other Spec Kit machinery first and attempt to
reconstruct governance afterward.** Removal is the last step, step 8.

### 14.2 The exact prerequisites

No deletion of `.specify/**` or any Spec Kit machinery is permitted until **every** item below is
satisfied and verified.

| # | Prerequisite | Verified by | Status after Phase 2 |
|---|---|---|---|
| **SK-1** | Every retained YAML rule has a permanent destination | Coverage matrix: 128 rows, 0 dropped, 0 `NOT_APPLICABLE` | **Met for the 5 YAMLs** |
| **SK-2** | Every rule in the explicit `<baseline-rules>` block has a destination | Matrix rows for that block | **BLOCKED — block not supplied (OQ-1)** |
| **SK-3** | Coverage is *validated*, not merely authored | Phase 7 validation | Phase 7 |
| **SK-4** | The new `.claude` governance exists on disk | `.claude/rules/`, `.claude/skills/`, `.claude/settings.json`, root `CLAUDE.md`, component `CLAUDE.md` files all present | Phase 3 |
| **SK-5** | Testing governance exists | `.claude/rules/40-testing.md` present and exercised | Phase 3 |
| **SK-6** | DB change gate exists | `.claude/rules/50-database.md` + `db-change` skill + H2 | Phase 4 |
| **SK-7** | LangGraph change gate exists | `.claude/rules/30-langgraph.md` + `langgraph-change` skill + H3 | Phase 4 |
| **SK-8** | ADR governance exists | `.claude/rules/70-adr.md` + `adr-author` skill | Phase 5 |
| **SK-9** | Functional knowledge extraction is **complete** | `docs/functional/implemented.md` exists and is populated from implementation artifacts only | Phase 6 — **directory does not exist today** |
| **SK-10** | The new governance has passed its validation phase | Phase 7 sign-off | Phase 7 |

### 14.3 Additional prerequisites this phase discovered

| # | Prerequisite | Why it is a prerequisite |
|---|---|---|
| **SK-11** | **Re-point the "constitution" references in enforcement config.** `dotnet/Directory.Build.props` says *"Constitution §.NET baseline"*; `ragcore/pyproject.toml` says *"constitution §Python baseline"* and *"the constitution permits mypy OR Pyright"*. | These comments point at the Spec Kit constitution. Deleting `.specify/**` orphans them and the mechanical enforcement loses its stated provenance. They must point at `.claude/rules/20-dotnet.md` / `21-python.md` **before** removal. |
| **SK-12** | **Decide the fate of the 10 `speckit-*` skills in `.claude/skills/`.** | They currently live inside `.claude/skills/` — the same directory the new governance skills will occupy. Removing `.specify/**` while leaving skills that invoke it produces broken skills. |
| **SK-13** | **Resolve `Synthia-Platform-Specification.md` (206 KB at repo root).** | An excluded, non-authoritative document that will outlive Spec Kit. Its status must be decided (archive, delete, or mark historical) so it is not mistaken for authority afterward. Raised as **OQ-3**. |
| **SK-14** | **Confirm `specs/**` disposition.** | `specs/` is Spec Kit's feature-spec tree. Whether it is removed, archived or retained as history is a human decision. |

### 14.4 The dependency, stated once

```
Phase 2 (this)  ->  Phase 3 (.claude build)  ->  Phase 4 (DB + LangGraph gates)
   ->  Phase 5 (ADR governance)  ->  Phase 6 (functional extraction)
   ->  Phase 7 (validation)  ->  Phase 8 (Spec Kit removal)

SK-2 blocks Phase 2 sign-off.
SK-1..SK-14 all block Phase 8.
```

---

## 15. Open questions requiring human decision (Output 15)

### OQ-1 — The `<baseline-rules>` block was not supplied — BLOCKING

The migration prompt names *"the complete `<baseline-rules>` block supplied in the migration prompt"*
as an authoritative input, and `<baseline-coverage>` requires a matrix row for every rule in it. **No
such block was present in the Phase 2 input.**

Phase 2 has delivered everything that does not depend on it: all three architecture documents are
mapped, all 128 rules from the five YAMLs are covered, and all six gates are defined. But:

- the coverage matrix **cannot be declared complete**;
- **SK-2 cannot be met**;
- therefore **Spec Kit retirement cannot be authorized**.

**Decision needed:** supply the `<baseline-rules>` block, or confirm in writing that no such block
exists and that the five YAMLs are the entire engineering baseline. Per `<engineering_baseline_files>`
— *"No supplied rule may be silently dropped"* — this cannot be assumed either way.

> **I did not attempt to reconstruct the block from `.specify/**` or any other excluded document.**
> `<source-policy>` forbids using excluded documents to recover rules absent from the supplied inputs.

### OQ-2 — No TypeScript / Angular / Electron engineering baseline exists

`apps/web/` (7 Angular projects) and `apps/desktop/` (Electron) are substantial components with no
supplied language rules. Phase 2 has scoped the 32 repository-wide principles to them and refused to
invent a baseline (§2.3).

**Decision needed:** (a) accept that only P1–P32 govern TypeScript, (b) supply a TS/Angular/Electron
YAML to be migrated the same way, or (c) commission one. Option (c) is **new baseline authoring**, not
migration, and belongs outside this migration.

### OQ-3 — Disposition of `Synthia-Platform-Specification.md`

A 206 KB document at the repository root, explicitly excluded from authority, which will survive Spec
Kit removal. **Decision needed:** archive, delete, or retain with an explicit "historical, not
authoritative" header. See SK-13.

### OQ-4 — Architecture document hygiene (AC-1, AC-4)

The three authoritative documents contain: cross-references to filenames that do not exist
(`identity-plane.md`, `RagAgent-Architecture.md` vs the `-final.md` actuals); duplicated headings in
A2 (§8.2, §11.1, §11.2); a numbering gap in A3 (§10 → §12); and two **non-authoritative** files sitting
in `docs/architecture/` alongside the authoritative three (`integrations-service-delta.md`,
`ragcore-langgraph-flow.md`).

**Decision needed:** these are editorial, not semantic — but the misfiled documents are a real
governance hazard, because a future reader will reasonably assume everything in `docs/architecture/`
is authoritative. Recommend relocating the two non-authoritative files or marking them clearly.
**Not fixed here** — Phase 2 does not modify files outside `docs/migration/`.

### OQ-5 — Status of ADRs embedded inside an authoritative architecture document

A3 §4 contains ADR-001…ADR-012 inline. Phase 2 treats them as authoritative because they are part of
an authoritative document, while `docs/adr/**` contents remain excluded. **Decision needed:** confirm
this reading. If ADR-001…012 are *not* authoritative, §10.4's "always requires an ADR" list needs
rederiving from A3's body text alone.

### OQ-6 — Unresolved reviewer notes inside A2

A2 §10 carries two open reviewer notes on the ServiceNow adapter (the tenant field *"is assumed right
now — confirm with business and Snow TAM"*). An authoritative document contains an authoritative
statement that a fact is unconfirmed. **Decision needed:** resolve the underlying question, or accept
that the integration architecture has a known open item that governance must route around.

### OQ-7 — Conformance findings are deferred, by instruction

Per `<important-boundary>`, Phase 2 did not resolve any implementation-vs-baseline disagreement.
Observations were recorded (e.g. ruff `N` and `T20`: this repo *exceeds* the baseline by selecting `N`,
and *falls short* on `T20`/PY4). **No baseline was altered and no application was altered.** These
belong to the conformance phase. **Decision needed:** confirm a conformance phase is scheduled — the
matrix's "Existing mechanism" column is its input.

---

## 16. Phase 2 completion check

| `<completion>` criterion | Status |
|---|---|
| All three architecture documents have explicit ownership | Met — §1.1, read off each document's own stated boundary |
| Every supplied engineering rule has an explicit destination | Met for the five YAMLs (128/128, 0 dropped) · **BLOCKED** for `<baseline-rules>` (OQ-1) |
| No supplied rule silently omitted | Met — 0 dropped, 0 `NOT_APPLICABLE_WITH_REASON` |
| Language-specific and repository-wide rules properly separated | Met — §2.1, enforced in both directions |
| DB and LangGraph change gates explicitly defined | Met — §9, §10, both with mandatory ordering |
| Testing is a first-class governance concern | Met — §12: own rule file, own gate, own hook candidate |
| ADR requirements explicit | Met — §11: five named mandatory triggers |
| Functional knowledge lifecycle explicit | Met — §13: implementation-artifacts-only |
| Spec Kit removal has clear prerequisites | Met — §14: SK-1…SK-14 |
| No decision derived from excluded repository documentation | Met — §0 |

**Phase 2 is complete except for OQ-1**, which is an input gap, not an unfinished deliverable.

### What this phase did NOT do, by instruction

- Did not modify application source code
- Did not delete any file
- Did not create the `.claude` implementation
- Did not remove or touch Spec Kit machinery
- Did not resolve any architecture conflict
- Did not resolve any implementation-vs-baseline disagreement
- Did not alter the engineering baseline
- Did not invent standards for TypeScript, Angular or Electron
