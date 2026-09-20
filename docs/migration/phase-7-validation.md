# Phase 7 — Claude Code Migration Validation

**Status of this document.** It is a validation and readiness record. It changed no application
source, test, migration, schema, contract, architecture document, ADR, CI definition or Spec Kit
asset. Where it reports a deviation, it reports it; it does not reconcile it.

---

## 1. Executive Result

### `NOT READY FOR PHASE 8`

Spec Kit retirement is **not authorized**. Four blockers stand, and two of them are structural
rather than clerical.

| # | Blocker | One-line statement |
|---|---|---|
| **B-1** | Engineering baseline is not migrated | **122 of 128** baseline rules point at `.claude/rules/` files that **do not exist**. Genuinely covered: **2**. |
| **B-2** | `<baseline-rules>` block still not supplied | The block named as an authoritative Phase 7 input was **not present in the Phase 7 execution context either**. SK-2 cannot be evaluated. |
| **B-3** | Governance hooks do not fire inside a git worktree | H2/H3 path normalization silently allows governed writes made from `.claude/worktrees/**`. Demonstrated live in this session. |
| **B-4** | TypeScript/Angular/Electron governance scope undecided | `apps/web` (7 Angular projects) and `apps/desktop` (Electron) carry **no governance text of any kind**. OQ-2 open. |

What is genuinely sound, and should not be re-litigated: the DB gate, the LangGraph gate, the ADR
gate and the functional-knowledge record are all well-built, internally consistent, and backed by
hooks that do what their rules claim. Every executable gate in the repository passes. The problem is
not the quality of what was migrated — it is that the **engineering baseline, which is the bulk of
the material Spec Kit held, was mapped but never written down.**

An important correction to the prior phases' framing: Phase 2 produced a complete 128-row *mapping*.
Phases 4–6 then built four *process* gates. Nobody built the eight *baseline* rule files the mapping
points at. The coverage matrix therefore describes an intended end state, not the repository.

---

## 2. Repository Revision Audited

| Item | Value |
|---|---|
| Revision audited | `2febbb0151d524de1c36b91f4d4fbe007d8a857c` |
| Branch at audit | `speckit-to-claude` (validation performed on worktree branch `phase-7-validation`, same commit) |
| Working tree at start | clean |
| Prior phase commits | Phase 4 `d2d2c9d`, Phase 5 `de27d81`, Phase 6 `2febbb0` |
| Tracked files | 831 |
| Platform | Windows 11, PowerShell + Git Bash; .NET 10.0.401, Python 3.11.9, uv 0.11.7, Node 24.14.1, Docker **running** |

Note: CI pins Node 22 (`.github/workflows/web.yml:30`); this audit ran Node 24. Web results are
therefore indicative, not CI-identical.

---

## 3. Claude Governance Inventory

Every artifact Phase 2/3 anticipated, classified. No missing artifact is silently accepted.

### 3.1 Present and valid

| Artifact | Evidence |
|---|---|
| `.claude/settings.json` | Registers three `PreToolUse` hooks under matcher `Write\|Edit\|MultiEdit\|NotebookEdit\|Bash`. Valid shape; `$schema` current. |
| `.claude/rules/30-langgraph.md` | 14.7 KB. Loaded into session context as project instructions. |
| `.claude/rules/50-database.md` | 11.4 KB. Loaded. |
| `.claude/rules/70-adr.md` | 17.7 KB. Loaded. |
| `.claude/rules/90-functional-knowledge.md` | 9.9 KB. Loaded. |
| `.claude/skills/{db-change,langgraph-change,adr-author,functional-update}/SKILL.md` | All four carry valid frontmatter (`name`, `description`, `argument-hint`, `user-invocable`, `disable-model-invocation`) — all currently-supported keys. All four are discoverable and were listed as invocable in this session. |
| `.claude/hooks/_guardlib.py`, `db_migration_guard.py`, `langgraph_change_guard.py`, `adr_structure_guard.py`, `test_guards.py` | Present, executable. `test_guards.py` → **188/188 checks passed**. |
| `docs/functional/implemented.md` | 1024 lines. Evidentially sound — see §12. |

**`.claude/rules/` auto-discovery is officially supported**, not emergent: Claude Code documents
`.claude/rules/*.md` as project instructions loaded at launch with the same priority as
`.claude/CLAUDE.md`. Confirmed empirically — all four files were injected into this session's
context with no `CLAUDE.md` present.

### 3.2 Missing but required

| Artifact | Why required | Consequence |
|---|---|---|
| `.claude/rules/10-principles.md` | Destination for **32** matrix rows (`principles#P1`–`P32`) | P1–P32 have no Claude-facing text anywhere |
| `.claude/rules/20-dotnet.md` | Destination for **50** matrix rows | Largest single gap |
| `.claude/rules/21-python.md` | Destination for **36** matrix rows | |
| `.claude/rules/40-testing.md` | Destination for **3** matrix rows | No testing baseline text; testing obligations survive only inside 30/50/70/90 |
| `.claude/rules/80-security-ops.md` | Destination for **1** matrix row | |
| `.claude/rules/00-authority.md` | Phase 2 §-named; the source-hierarchy rule | Authority hierarchy is restated ad hoc in each of the four rules instead of once |
| `.claude/rules/22-web-typescript.md` | Phase 2 §-named | See B-4 / §5.3 |
| `.claude/rules/60-architecture-gates.md` | Phase 2 §-named | |
| `CLAUDE.md` (root) | Phase 2 §-named | See 3.3 |

### 3.3 Missing — required status is a human decision

| Artifact | Assessment |
|---|---|
| `CLAUDE.md` | **Not strictly required** — `.claude/rules/` loads without it. But its absence costs: visibility in `/memory` and `/context`, `@path` import syntax, `CLAUDE.local.md`, and `InstructionsLoaded` hook firing for unconditional rules. Recommended, not blocking. |
| `.claude/skills/architecture-conformance/SKILL.md` | **Not required for retirement.** Phase 7 establishes that architecture conformance is currently a reporting activity (§6), not a procedure Claude executes. No gate depends on it. Classified: *intentionally not required, pending the human decision in §17 D-7.* |

### 3.4 Present but out of scope of the migration

`.claude/skills/speckit-*` — 10 skills, still present and functional. Disposition is SK-12 (§15).

---

## 4. Engineering Baseline Coverage

### 4.1 Sources and rule counts

| File | Authored `id:` keys | ID scheme |
|---|---|---|
| `principles.yaml` | 32 | `principles#P1`–`P32`, contiguous |
| `python.yaml` | 9 | `P-PY-S1`–`S3`, `P-PY-1`–`6` |
| `python_lang.yaml` | 25 | `lang/python#PY1`–`PY25`, contiguous |
| `dotnet.yaml` | 12 | `P-DN-S1`–`S5`, `P-DN-1`, `1b`, `2`–`6` |
| `dotnet_lang.yaml` | 37 | `lang/dotnet#DN1`–`DN37`, contiguous |
| **Total authored IDs** | **115** | |

The Phase 2 matrix reports **128**. The difference is method, not omission: the matrix promotes
unkeyed `toolchain:`/`baseline:` entries to rows (94 keyed + 18 + 16 = 128). Both counts are
defensible; **no YAML rule is absent from the matrix.** This report uses 128 to stay comparable with
Phase 2.

### 4.2 The headline result

| Measure | Count | % |
|---|---|---|
| Destination file **exists today** | **6** | 4.7% |
| Destination file **does not exist** | **122** | 95.3% |
| **Rule genuinely present in an existing destination** | **2** | **1.6%** |

Destination distribution:

| Destination | Rows | Exists? |
|---|---|---|
| `.claude/rules/20-dotnet.md` | 50 | **NO** |
| `.claude/rules/21-python.md` | 36 | **NO** |
| `.claude/rules/10-principles.md` | 32 | **NO** |
| `.claude/rules/70-adr.md` | 4 | YES |
| `.claude/rules/40-testing.md` | 3 | **NO** |
| `.claude/rules/90-functional-knowledge.md` | 2 | YES |
| `.claude/rules/80-security-ops.md` | 1 | **NO** |

Zero rows point at `30-langgraph.md` or `50-database.md` — correctly, as those are process gates,
not baseline destinations.

Cross-tabulated against the matrix's own mechanical-enforcement column:

| | Mech=Y | Mech=Partial | Mech=N | Total |
|---|---|---|---|---|
| Destination EXISTS | 0 | 2 | 4 | 6 |
| Destination MISSING | 83 | 18 | 21 | 122 |

Two consequences worth stating plainly:

- **83 rules survive only because ruff/mypy/Roslyn/architecture tests independently enforce them.**
  They are enforced, but not *governed* — nothing tells Claude the rule exists, so nothing stops
  Claude proposing a change that a gate then rejects for reasons it cannot explain.
- **39 rules (21 `N` + 18 `Partial`) have neither rule text nor a complete gate.** These are
  unguarded in both directions today.

### 4.3 Semantic preservation — the six rules that reached an existing file

| Baseline rule | Destination | Verdict |
|---|---|---|
| `dotnet.yaml#P-DN-5` — ADR: MADR, `docs/adr/`, sequential numbering, status field | `70-adr.md` | **PRESERVED AND STRENGTHENED** — narrowed to four-digit kebab filenames (`:199`), closed status vocabulary, human-acceptance gate. Strictly stronger. |
| `python.yaml#P-PY-5` — identical | `70-adr.md` | **PRESERVED AND STRENGTHENED** |
| `dotnet.yaml#P-DN-4` — Conventional Commits + SemVer | `70-adr.md` | **MISSING (dropped).** `grep -riE 'conventional commit\|semver'` over `.claude/` = 0 hits. `70-adr.md:113` says changing "commit or versioning convention" needs an ADR but never states the convention. |
| `python.yaml#P-PY-4` — identical | `70-adr.md` | **MISSING (dropped)** |
| `dotnet.yaml#P-DN-6` — README/docs: Diataxis, C4 diagrams, quickstart + ADR pointer | `90-functional-knowledge.md` | **MISSING and ALTERED (scope-mismatched).** 0 hits for Diataxis/C4/quickstart. `90-*` governs only `docs/functional/implemented.md` — a different document with a different purpose. |
| `python.yaml#P-PY-6` — identical | `90-functional-knowledge.md` | **MISSING and ALTERED** |

**Four of the six rules whose destination exists were nonetheless dropped.** This is why the "6"
in §4.2 collapses to "2".

### 4.4 Semantic-preservation defects in the wider set

| Defect class | Instance | Classification |
|---|---|---|
| Repository-wide principle narrowed to a domain instance | `principles#P17` (least privilege) survives only as the DB principal separation in `50-database.md:106-110`. Nothing carries it to `apps/web`, `apps/desktop`, `integrations`. | `ALTERED` (narrowed) |
| Positive obligation replaced by a meta-gate | `lang/dotnet#DN21` (every `#pragma warning disable` scoped + justified). `70-adr.md:117` makes adding an unjustified pragma an ADR trigger but never states the requirement. The meta-gate assumes the reader already knows the rule. | `ALTERED` (weakened in effect) |
| Language scoping unanchored | Every `lang/python#*` and `lang/dotnet#*` rule. The matrix declares "language scoping preserved", but with `20-dotnet.md`/`21-python.md` absent, **no file carries the scoping statement.** | `MISSING` |
| No traceability | `grep -rn 'principles#\|lang/dotnet\|lang/python\|P-DN\|P-PY'` over `.claude/` → **zero matches.** No migrated rule, skill or hook cites a baseline rule ID, so baseline→destination traceability is not machine-checkable anywhere. | `MISSING` |

### 4.5 Errors in the Phase 2 matrix's enforcement column — independently verified

Verified directly against `dotnet/.editorconfig` during this audit:

| Matrix claim | Actual | Impact |
|---|---|---|
| `lang/dotnet#DN8` (ConfigureAwait) — "CA2007 severity=error", status `MIGRATED_AND_MECHANICALLY_ENFORCED` | `.editorconfig:84` — `CA2007.severity = none`, commented "off deliberately, not by oversight" | **DN8 is not enforced at all.** A deliberate baseline relaxation with no ADR — itself an ADR trigger under `70-adr.md` §70.2 B(1). |
| `lang/dotnet#DN31` — "CA1848 severity=error" | `.editorconfig:94` — `severity = suggestion` | Not build-failing; suggestions do not become errors under TWAE. |
| `lang/dotnet#DN16` — "CA1062 severity=error" | `.editorconfig:92` — `severity = warning` | Build-failing only via `TreatWarningsAsErrors=true`; stated mechanism inaccurate and would silently stop working if TWAE were scoped down. |

Also verified: `T20` (the `print` ban, `lang/python#PY4`) is **absent** from ruff `select`
(`ragcore/pyproject.toml:75`) — the rule is fully unguarded in both directions.

### 4.6 Coverage table — status roll-up

Per-rule rows are in `docs/migration/phase-2-coverage-matrix.md`; this is the Phase 7 verdict over
them, using the required status vocabulary.

| Status | Count | Meaning here |
|---|---|---|
| `MIGRATED_AND_MECHANICALLY_ENFORCED` | **0** | No rule is both written in a rules file and mechanically gated. |
| `MIGRATED_TO_RULE` | **2** | `P-DN-5`, `P-PY-5` (also H5-enforced, so arguably the only two fully governed rules). |
| `MECHANICALLY_ENFORCED` (gate only, no rule text) | **83** | Enforced by ruff/mypy/Roslyn/architecture/boundary/contract/migration gates. |
| `REQUIRES_FUTURE_ENFORCEMENT` | **18** | Partial gate, no rule text. |
| `MISSING` | **21** | No gate, no rule text. |
| `ALTERED` | **4** (+3 wider defects in §4.4) | `P-DN-4`, `P-PY-4`, `P-DN-6`, `P-PY-6`. |
| `CONFLICTING` | **0** | No duplicate/contradictory rule text found in `.claude/`. |

No status was invented to conceal a gap.

---

## 5. Explicit Baseline Coverage

### 5.1 The `<baseline-rules>` block — BLOCKING INPUT PROBLEM

Phase 7's instructions direct that the statement in
`docs/migration/phase-2-authority-model.md` §3.4 — that the block was absent — must not be
inherited, and that the actual block supplied with the migration task must be used.

**The `<baseline-rules>` block was not present in the Phase 7 execution context either.** The Phase 7
task text names it as an authoritative input and describes its contents, but no such block was
supplied. This is reported, as instructed, as a **blocking validation-input problem** — not as a
finding that the block does not exist.

Explicitly, and in line with the source policy:

- The block was **not** reconstructed from `.specify/**`.
- The block was **not** reconstructed from the Spec Kit constitution.
- The block was **not** inferred from implementation.
- The five YAMLs were **not** silently treated as the complete baseline.

**Explicit `<baseline-rules>` coverage: 0 rows — block not supplied. SK-2 cannot be evaluated.**

Phase 2's own record, quoted verbatim for continuity (`phase-2-authority-model.md:250-254`):

> ### 3.4 The baseline-rules input gap
>
> `<baseline-coverage>` requires a row for **every** rule in the explicit `<baseline-rules>` block. **That
> block was not present in the Phase 2 input.** The matrix covers the five YAMLs completely and the
> explicit baseline not at all. This is **OQ-1** and it is **blocking for Phase 2 sign-off** — see §15.

and OQ-1 (`:813-826`):

> **Decision needed:** supply the `<baseline-rules>` block, or confirm in writing that no such block
> exists and that the five YAMLs are the entire engineering baseline. Per `<engineering_baseline_files>`
> — *"No supplied rule may be silently dropped"* — this cannot be assumed either way.

Phase 7 reaches the same conclusion independently, from a second failed attempt to obtain the input.
The decision remains a human one (§17, D-1).

### 5.2 Distinguishing the two failures

These are different problems and should not be conflated in remediation:

- **B-2** (this section) is an *input* failure — a required source was never delivered.
- **B-1** (§4) is an *execution* failure — a source that *was* delivered, in full, was mapped and
  then not written into the governance tree.

Resolving B-2 does not resolve B-1, and vice versa.

### 5.3 TypeScript / Angular / Electron

**Reported, not invented.** No TS/Angular/Electron rule family was authored in Phase 7.

Confirmed: **none of the five YAMLs contains a TypeScript, Angular or Electron rule.** A
case-insensitive grep for `typescript|angular|electron|javascript|node\.js|npm|eslint|frontend|web`
across all five files returns exactly one line, a false positive on the substring `ts` in a Python
example (`python_lang.yaml:365`, `datetime.fromtimestamp(ts, ...)`).

`principles.yaml` is language-agnostic by construction (`applies_when: [always]`). `python.yaml:3`
scopes itself `language == python`; `dotnet.yaml:3` scopes `language in [dotnet, csharp]`.

Phase 2 already recorded this (`phase-2-authority-model.md:182`): *"**None of the five supplied YAML
files contains a single TypeScript, Angular or Electron rule.**"*

**Intended governance: STILL UNRESOLVED (OQ-2).** The three candidate answers —
*principles-only*, *a separately supplied TS baseline*, or *deliberately ungoverned* — are a human
decision (§17, D-2). What is factual today:

- `.claude/rules/22-web-typescript.md` does not exist.
- `apps/web` (7 Angular projects) and `apps/desktop` (Electron) therefore carry **no governance text
  of any kind** — not even the P1–P32 scoping statement Phase 2 planned for that file.
- Both surfaces nonetheless have **strong mechanical gates with no baseline behind them**:
  `.github/workflows/web.yml` (eslint, prettier, `tsc -b`, build, test, a11y, CSP) and
  `desktop.yml` (Electron security suite). This is the mirror image of §4.2's 83 rules — here the
  gate exists and the rule never did.

---

## 6. Architecture Conformance

Authority: A1 `identity-plane-final.md`, A2 `Synthia-OverallArchitecture-final.md`,
A3 `RagAgent-Architecture-final.md`. `ragcore-langgraph-flow.md` and `integrations-service-delta.md`
were **not** treated as authority.

| Domain | Auth | Section | Expected | Observed | Evidence | State | Severity | Human action |
|---|---|---|---|---|---|---|---|---|
| Tenant filter on retrieval | A3 | §9.6 | Non-bypassable `tid` filter | `RetrievalPort.search` takes `TenantContext` as required first positional; filter built from context alone; no OData filter param exists | `application/ports.py:405-420`; `retrieval/search.py:64,80`; `grounding.py:56` | **CONFORMS** | — | none |
| LLM owns no execution authority | A3 | §6.3 | Model cannot set tenant/requester/approval/identity | `ProposedOperationView` has no treatment/approved/roles key; asserted by test | `state.py:169-181`; `tests/governance/test_authority_boundary.py:163-169` | **CONFORMS** | — | none |
| No side effect from an agent node | A3 | §6.3 | Only governed path performs consequential ops | One edge reaches `execute`; re-checks disposition, raises `UnauthorizedExecutionError`; connector ports unbound and test-enforced | `builder.py:116-125`; `execution.py:56-61`; `tests/architecture/test_no_connector_in_ragcore.py` | **CONFORMS** | — | none |
| Treatment monotonic narrowing | A3 | §6.3 | Treatment may not widen | `TreatmentWidenedError` in reducer | `state.py:290-305` | **CONFORMS** (exceeds A3) | — | none |
| Execution re-reads durable work item before acting | A3 | §6.3, §7.4 | Re-read work item; verify tenant/action/target/approval/validity at point of effect | `execute` never touches `deps.work_items`; reads checkpoint state + run context only. `claim_for_execution` exists but is called only from `messaging/sample_flow.py:150`, outside the graph | `graph/nodes/execution.py:47-99`; `execution/claim.py:49-75` | **DEVIATES** | High | §17 D-4 |
| Signed / idempotent execution | A3 | ADR-011 | Idempotency key from `request_id`; signed payload | Key is `f"{work_item_id}:{identity}"`. Signing entirely absent — no `SigningProfile`/`sign_payload` anywhere; `ToolExecutionPort.invoke` has no signing param | `execution.py:76`; `ports.py:477-490` | **DEVIATES** | High | §17 D-4 |
| Two-index retrieval | A3 | ADR-003, §9.1 | Incident + SOP indexes | One index (`index_name = "synthia-knowledge"`). Word-boundary grep for `sop` across `ragcore/src/**/*.py` → **0 hits** | `config/settings.py:215` | **DEVIATES** | Medium | §17 D-4 |
| Typed resolution | A3 | ADR-004 | `resolution_type` {ACTION,SOP,NONE}, SOP terminal | No `resolution_type`, no `resolution_ref`, no SOP branch | `state.py:379-431` | **DEVIATES** | Medium | §17 D-4 |
| Clarify loop w/ in-loop probe | A3 | ADR-007, §7 | Bounded loop, probe retrieval, question selection | `clarify` node registered with an outgoing edge but **no inbound edge** — dead topology. No `clarify_iterations`, no probe; `retrieve` is a single committing pass | `builder.py:70,92`; `grounding.py:34` | **DEVIATES** | Medium | §17 D-4 |
| Memory architecture | A3 | ADR-008 | Short-term checkpoint + namespaced long-term store | Checkpoint half conforms (`tenant:user:session` keying). **Long-term `BaseStore` half absent** — no store, no `user_profile`, no `recalled_incidents` | `threads.py:32-44`; `host.py:128-140` | **PARTIALLY_CONFORMS** | Medium | §17 D-4 |
| Field-scoped embedding | A3 | ADR-003, §9.2 | Field-scoped embedding + chunking | Implemented, **unbound** — no production caller | `retrieval/embedding.py:49,60,110` | **PARTIALLY_CONFORMS** | Low | §17 D-4 |
| Hybrid retrieval / rerank | A3 | §9.3, §9.4 | Sparse leg load-bearing; rerank with cost knob | Both implemented; referenced **only by unit tests**. Composition binds dense-only `AzureAiSearchRetrieval` | `retrieval/hybrid.py:181`, `rerank.py:156`; `composition.py:261` | **PARTIALLY_CONFORMS** (test-only) | Medium | §17 D-4 |
| Confidence + margin | A3 | §9.5 | Global constants, `>=`, no probability | `MINIMUM_TOP_SCORE=0.45`, `MINIMUM_MARGIN=0.08`, both `>=` | `retrieval/confidence.py:46,57` | **CONFORMS** (dense leg) | — | none |
| Per-tenant tool injection | A3 | ADR-009 | Tools bound per tenant entitlement | No `tool_binding` state, no binding mechanism | `state.py:379-431` | **DEVIATES** | Medium | §17 D-4 |
| Approval verdict source | A3 | §6.3, §8 | Only authenticated Staff API | Graph never writes a verdict; `record_verdict` called from no graph code; sole ingress is the Staff route, which is **501** | `dependencies.py:48-49`; `api/staff/routes.py:91-108` | **CONFORMS as designed; UNVERIFIED in operation** | Medium | §17 D-4 |
| Work-item immutability at DB boundary | A1 | §12.2 | Named identity fields immutable at DB permission boundary | 3 of 8 named fields + action/target protected; approval fields protected in app code only | see §9 | **PARTIALLY_CONFORMS** | High | §17 D-3 |
| DB permission separation | A1/A2 | §12.2, §8.1 | Migration job DDL, runtime DML/SELECT | Four roles, enumerated grants, separate DSNs | `0019_database_principals.py`; `build/docker/migrate.job.yaml` | **CONFORMS** | — | none |
| Checkpoint store ownership | A2 | §8.1 | Single durable checkpoint store, Azure Postgres | One store, `langgraph` schema, no FK across boundary, no startup DDL | `checkpointer.py:46,118-119,164-168` | **CONFORMS** | — | none |
| Graph state vocabulary | A3 | §6.2 | A3 names | Implementation names differ **and ~2/3 of the vocabulary is absent** | §10.2 | **DEVIATES** | Medium | §17 D-4 |
| Eval harness / release gates | A3 | ADR-012 | Harness gates releases | No harness reachable from the graph surface; none found in CI | — | **UNVERIFIED** | Medium | §17 D-4 |

**No `ARCHITECTURE_CONFLICT` was found.** A1, A2 and A3 do not contradict one another anywhere this
audit examined; A3 §6.3's deferral to A1 on identity is a deferral, as `30-langgraph.md` states.

**Framing note.** Every `DEVIATES` above is the gap between a *scaffold* and a *target
architecture*, not a wrong turn. The repository is an early-stage scaffold that has built its
governance, persistence and boundary layers first. That is a coherent strategy. It does mean
`implemented.md`'s classification discipline is carrying a lot of weight, and it is carrying it well.

---

## 7. Production Reachability

Phase 6's central claim was re-verified against current code rather than assumed.

### 7.1 The Phase 6 claim — STILL TRUE, verbatim

| Step | Evidence |
|---|---|
| `composition.py` binds `execution=None` | `ragcore/src/ragcore/config/composition.py:307-310` — `case_system=None, directory=None, execution=None, discovery=None`, unconditional, inside the sole production `build_container()` |
| `graph_dependencies()` returns `None` | `composition.py:384-395` — `container.execution` is in `required`; `if any(binding is None ...): return None`. Always true. (`container.retrieval` is a second independent cause.) |
| `run_host` absent | `api/app.py:139-146` — `app.state.run_host = None`; the `if deps is not None:` branch never fires, so the graph is **never compiled** and the durable checkpointer is **never opened** in any deployed process |
| Customer messages → empty SSE | `api/customer/sessions.py:149-159` — `empty_stream(...)` unless `isinstance(host, RunHost)`; `streaming.py:134-145` yields only `done`. Test: `tests/contracts/test_api_surface.py:353-360` |

### 7.2 Two further blockers Phase 6 did not name

Even with a bound `RunHost`, governance and execution remain unreachable from `POST /messages`:

1. **`propose` always returns `{}`** (`graph/nodes/grounding.py:130-143`). `_route_after_propose`
   (`builder.py:156-163`) returns `END` when `proposal is None`, and `_initial_state`
   (`sessions.py:193-214`) seeds no proposal. `govern`, `await_consent`, `await_approval`, `execute`
   and `verify` are therefore unreachable **by construction**.
2. **`clarify` has no inbound edge** (`builder.py`) — the clarify loop is dead topology.

Also: `graph/nodes/clarification_interrupt.py` is an **orphan module**, registered nowhere.

### 7.3 Reachability table

| Capability | Source | Composed | Reachable from prod entry point | Classification |
|---|---|---|---|---|
| Session creation | `api/customer/sessions.py:85-95` | n/a | Yes — `POST /sessions` 201 | **PRODUCTION-REACHABLE but non-durable** (returns `uuid4()`, persists nothing) |
| Customer message processing | `sessions.py:116-166` | endpoint yes, host no | Yes, yields only `event: done` | **WIRED BUT INERT** |
| Graph execution | `graph/builder.py:51-136`, `host.py:143-199` | **No** | **No** | **TEST-ONLY** |
| Clarification loop | `conversation.py:44-86`; `answers.py` | No | **No** — no inbound edge; route 501 | **WIRED BUT INERT + TEST-ONLY** |
| Retrieval | `retrieval/search.py:132` | conditional | **No** — graph never runs | **IMPLEMENTED BUT UNBOUND** |
| Governance decision | `graph/nodes/governance.py:40-92` | No | **No** | **TEST-ONLY** |
| Consent | `api/customer/routes.py:89-105` | repo bound, unread | **No** — 501 | **WIRED BUT INERT** |
| Approval request/verdict | `api/staff/routes.py:91` | repo bound, unread | **No** — 501 | **WIRED BUT INERT** |
| Action execution | `graph/nodes/execution.py:44-101`; `execution/executor.py:129` | **No** | **No** | **TEST-ONLY** |
| Verification | `graph/nodes/execution.py:104-122` | No | No | **NAME-ONLY / inert** (`return {}`) |
| Work-item lifecycle | `application/sessions.py:230` | repo bound; `SessionLifecycle` instantiated **nowhere** | **No** | **IMPLEMENTED BUT UNBOUND** |
| Realtime / SSE | `streaming.py:64-145`; `negotiate.py:79-96` | notifier `None` | SSE transport yes (inert content) | transport **PRODUCTION-REACHABLE (inert)**; SignalR **UNBOUND** |
| Staff operations | `api/staff/routes.py` ×4 | n/a | 501 | **WIRED BUT INERT** |
| Customer operations | `api/customer/routes.py` ×3 | n/a | 501 | **WIRED BUT INERT** |
| Customer feedback | `api/customer/feedback.py:77-157` | **Yes** | **Yes** — 204/404, writes in a UoW | **PRODUCTION-REACHABLE** |
| .NET read views (12 routes) | `CustomerViewEndpoints.cs`, `StaffViewEndpoints.cs` | **Yes** | **Yes** | **PRODUCTION-REACHABLE** |

**Only three capabilities are production-reachable and functional:** customer feedback, the twelve
.NET read-view routes, and session creation (non-durable).

### 7.4 Integrations

| Integration | Classification | Evidence |
|---|---|---|
| Graph adapter (MS Graph) | **IMPLEMENTED BUT UNBOUND** | `connectors/graph/adapter.py:66` (150 lines, real httpx + MI token); absent from the Integrations `Container` entirely |
| MCP client | **IMPLEMENTED BUT UNBOUND; behaviorally UNVERIFIED** | `mcp/client.py:91` (219 lines); constructed **nowhere**, and **no test exists** |
| ServiceNow | **IMPLEMENTED BUT UNBOUND** | `connectors/servicenow/adapter.py:71`; built only `if secrets is not None`, and the sole production call is `build_container()` with no secrets → route returns **503** |
| Notifications (SignalR) | **IMPLEMENTED BUT UNBOUND; UNVERIFIED** | `notifications/signalr.py:92`; never constructed, **no test** |
| Content safety | **IMPLEMENTED BUT UNBOUND** | `model/safety.py:194`; `composition.py:257` binds the raw adapter, **not** wrapped in `SafeModel`. Its own docstring (`safety.py:16`) claims the composition root binds `SafeModel` — **that claim is false** |
| Hybrid retrieval | **IMPLEMENTED BUT UNBOUND (test-only)** | `retrieval/hybrid.py:181`; referenced only by `tests/unit/test_hybrid.py` |
| Reranking | **IMPLEMENTED BUT UNBOUND (test-only)** | `retrieval/rerank.py:156`; referenced only by `tests/unit/test_rerank.py` |
| ExecutionLeg | **TEST-ONLY** | Two implementations; neither constructed in any `src/` or `workers/` module |
| Duo | **NAME-ONLY** (deliberate) | `connectors/duo/__init__.py:21-26` — two `Final` constants; depends on the unbound MCP client |
| OneLogin | **NAME-ONLY** (deliberate) | `connectors/onelogin/__init__.py:28-38` — same |

### 7.5 Workers

**No worker is a live entry point anywhere in the platform.** All seven `main()` functions raise
`NotImplementedError`: `resume_worker.py:144`, `outbox_dispatch.py:199`,
`integration_result_worker.py:203`, `expiry_sweep.py:103`, `retention_sweep.py:245`,
`ingestion_run.py:120`, and `integrations/workers/command_consumer.py:100`.

Consequence: no outbox dispatch, no resume servicing, no retention/expiry sweeps, no ingestion, no
integration command/result consumption in any deployed process. **There is no non-live resume driver,
and no code path anywhere calls `Command(resume=...)`.**

### 7.6 Two docstrings that are not evidence (rule 90.2)

- `graph/host.py:91` and `api/customer/sessions.py:246` both cite `tests/unit/test_run_host.py`.
  **That file does not exist**; no test references `RunHost` at all.
- `model/safety.py:16` asserts a composition-root binding that does not exist (§7.4).

---

## 8. API Contract Conformance

| Check | Result |
|---|---|
| Contracts location | `build/contracts/{dotnet,integrations,ragcore}/*.openapi.json` + `approved-breaking-changes.json`, policy at `build/policy/openapi-disclosure.json` |
| Generation | Emitted **from the running services**, not maintained by hand: `ragcore/scripts/emit_contracts.py`, `integrations/scripts/emit_contracts.py`, `Synthia.ContractTests/OpenApiEmissionTests` |
| Deterministic CI check | **Yes** — `.github/workflows/contracts.yml` job `openapi`: emit → **emit again and require byte-identical output** → validate → **prove the guards catch a planted violation** → compare against a pre-run copy of the committed contracts → **fail if committed contracts are stale** → publish |
| Declared but not mapped | **None.** All 32 operations across six contracts map 1:1 to route registrations |
| Mapped but unimplemented | **13 routes return 501** — 3 customer work-item, 1 answers, 3 sample-flows, 4 staff, 2 workload |
| Contract overclaiming | **None for the 501 routes.** Each declares `501` and **no 2xx at all**, because `NOT_IMPLEMENTED_ROUTE` pins `status_code=501` on the decorator. Contract and implementation agree |
| Behavioral gap | **One.** `POST /sessions/{sessionId}/messages` declares `200` with no statement about stream content; the runtime satisfies it with a stream carrying only `done`. Contract-conformant, but a 200 SSE response reads as promising more. Already recorded at `implemented.md` §6.9/§6.10 |
| Spec Kit leakage into a published artifact | **Yes, one.** `build/contracts/ragcore/customer.v1.openapi.json:435` embeds ``specs/001-platform-scaffold/tasks.md``, sourced from the docstring at `ragcore/src/ragcore/api/customer/sample_flows.py:119`. Fixing it requires editing the docstring **and re-emitting**, which the staleness gate will then demand |

No contract was modified during this audit. Required cleanup is listed separately in §18.

---

## 9. Database Conformance

| # | Area | State | Evidence |
|---|---|---|---|
| 1 | Migration chain `0001`–`0025`, linear, no gaps | **CONFORMS** | `alembic heads` → `0025_integrations_recovery_views (head)`; `alembic branches` empty. Verified both dynamically (no DB needed for these commands) and by static `down_revision` analysis |
| 2 | **Single head** | **CONFORMS** | as above |
| 3 | Downgrade coverage 25/25, no no-ops | **CONFORMS** | Two deliberately partial and documented in-file: `0001` leaves the `platform` schema (it holds `alembic_version`); `0021` leaves the `synthia_integrations` role (may be referenced by an MI mapping the revision cannot see) |
| 4 | Alembic owns `platform`; `langgraph` excluded from autogenerate | **CONFORMS** | `persistence/autogenerate.py:49-83` (both `include_name` and `include_object`), wired at `migrations/env.py:131-149`. Tested **without a database** by `tests/migrations/test_schema_isolation.py`, which AST-parses `env.py` to prove both filters are installed |
| 5 | No startup DDL; gated job only | **CONFORMS** | `checkpointer.py:118-119` explicitly does not call `setup()`; sole caller is `provision_checkpoint_schema` via `scripts/provision_checkpoint_schema.py`, run by `build/docker/migrate.job.yaml` after `alembic upgrade head`. Structurally enforced: `tests/checkpoint/test_durable_checkpointer.py:208` asserts `setup_callers == ["provision_checkpoint_schema"]` |
| 6 | Checkpoint schema creation attribution | **PARTIALLY_CONFORMS** | `setup()` creates *tables*; the `langgraph` *schema* is created by `checkpointer.py:164-165`. Documented in-file; the rules' phrasing is slightly imprecise. Non-material |
| 7 | Principal separation — migrator DDL / runtime DML / monolith view-SELECT | **CONFORMS** | `0019_database_principals.py:111-143`; runtime's only schema-level grant is `USAGE`. Separate DSNs at the connection level. Grants enumerated, not wildcarded; no default privileges |
| 8 | Python ORM↔DDL mechanical check | **CONFORMS** | `pytest_alembic` `test_model_definitions_match_ddl` at `tests/migrations/test_migrations.py:31,40`, strengthened by `compare_server_default=True, compare_type=True` (`env.py:140-143`); runs in CI against `postgres:17` |

### 9.1 Work-item immutability vs A1 §12.2 — key finding

`0017_work_item_immutability.py` installs a `BEFORE UPDATE ... FOR EACH ROW` trigger protecting:
`tenant_id`, `session_id`, `requested_by_oid` (never changeable) and `case_reference`,
`governed_action`, `target` (write-once, `IS DISTINCT FROM`, correctly blocking value→null).

| A1 §12.2 named field | DB-protected? | Note |
|---|---|---|
| `tenant_id` | **YES** | `0017:44-48` |
| `requested_by_oid` | **YES** | `0017:56-60` |
| requested action | **YES** (`governed_action`) | `0017:69-74` |
| target | **YES** | `0017:76-80` |
| `requester_role` | **N/A** | **No such column exists** on `platform.work_item`. Roles live on `approval.decided_by_roles` and `governance_record.accepted_roles` |
| approval requirement | **NO** | `work_item.approval_state`, `operation.treatment`, `governance_record.default_treatment` are UPDATE-able by the runtime with no DB guard |
| `approved_by_oid` (once recorded) | **NO** | `approval.decided_by_oid` — different table, **no trigger at all** |
| `approved_at` (once recorded) | **NO** | `approval.decided_at` — same |

Only one trigger exists in the entire migration set (`grep "CREATE TRIGGER"` → `0017` only). What
protects approval decisions today is a `CHECK` constraint and a `UNIQUE (work_item_id)` giving
first-valid-verdict-wins **on insert** — but `synthia_ragcore` holds `UPDATE` on `approval`
(`0019:66`), so nothing at the database layer prevents an `UPDATE` of `decided_by_oid`/`decided_at`/
`verdict` on an existing row. The immutability assertions that do exist are application/unit-level.

A1 §12.2 requires enforcement *"at the database permission boundary, not only in application code."*
**Classification: `DEVIATES`. Severity: High.** This is an ADR trigger under `70-adr.md` §70.2 D(1)
and D(3) **if anyone proposes to act on it** — Phase 7 reports it only (§17, D-3).

`session_id` is protected though A1 does not name it — a superset, not a weakening.

### 9.2 EF Core / Alembic — mechanical drift check

| Claim | State |
|---|---|
| .NET uses EF Core for data access | **Confirmed** |
| Alembic owns all schema migrations | **Confirmed** |
| Enforcement prevents .NET migrations | **Confirmed** — `NoMigrationTests.cs` bans `Migrate()`/`EnsureCreated()`, any `Migrations` folder, and any `Migration`/`ModelSnapshot` subclass |
| **Any mechanical check ties EF models to the Alembic-owned schema** | **NO — none exists** |

The seam is precise: `NoMigrationTests.cs` checks each EF entity's view name against
`PublishedViews.All` — a **hand-maintained C# constant list**
(`Synthia.Persistence/Views/PublishedViewRows.cs:15-33`). The authoritative view definitions live in
Python (`ragcore/src/ragcore/persistence/views.py`, `0018_published_views.py`, grants at
`0019:74-86`). **Nothing compares the two lists**, and nothing compares the EF row types' columns
and types against the actual view columns.

Reinforcing evidence: `ReadContextFactory.cs:24` deliberately opens no connection
(`Host=architecture-tests.invalid`); `Testcontainers.PostgreSql` is declared in
`Directory.Packages.props:70` but **referenced by no `.csproj`**; `dotnet.yml` has no Postgres
service. A renamed or re-shaped view would leave both sides compiling and both suites green,
surfacing only at runtime query time.

This confirms empirically the deviation `50-database.md` §50.7 already records. **Not corrected here.**

---

## 10. LangGraph Conformance

### 10.1 Actual topology

14 nodes registered (`builder.py:68-81`): `intake`, `converse`, `clarify`, `retrieve`, `ground`,
`guardrail`, `propose`, `classify`, `govern`, `await_consent`, `await_approval`, `execute`,
`verify`, `close`. Entry: `START → intake` (`:86`).

Conditional edges — three:

| Source | Predicate | Branches |
|---|---|---|
| `guardrail` | `_route_after_guardrail` (`:139-153`) on `session_state` | `{propose, close}` |
| `classify` | `_route_after_propose` (`:156-163`) on `proposal is not None` | `{govern, END}` |
| `govern` | `route_after_govern` (`governance.py:135-153`) on `governance.disposition` | `{execute, await_consent, await_approval, close}` |

Terminal: `verify → END`, `close → END`, and the `classify → END` branch.

**Topology findings:** `clarify` is registered and has an outgoing edge but **no inbound edge** — no
clarify loop exists in the built graph. Both suspension nodes return to `govern`, not forward to
`execute`. `nodes/clarification_interrupt.py` is registered nowhere (dead code).

### 10.2 State shape

`AgentState(TypedDict, total=False)` — 15 channels (`state.py:414-431`): `tenant_id`, `session_id`,
`work_item_id`, `correlation_id`, `session_state`, `pending_interrupt`, `conversation` (`_append`),
`retrieved` (`_append`), `grounding`, `classification`, `proposal`, `governance`
(`seal_governance`), `decision` (`seal_human_decision`), `execution` (`seal_execution`),
`verification` (`seal_verification`).

Reducers: `_seal` accepts identical replay, raises `StateChannelSealedError` on a differing second
write. `seal_governance` enforces monotonic narrowing via `is_narrowing`, raising
`TreatmentWidenedError` on widening. `seal_human_decision` keeps the **first** record.

**Phase 7 correction to the recorded deviation.** `30-langgraph.md` §30.7 maps implementation
`decision` ↔ A3 `approval` and `execution` ↔ A3 `consent`. In the code, A3's `approval` **and**
`consent` both land in the single `decision` channel (discriminated by `HumanDecisionRecord.kind`,
`state.py:212`), while `execution` + `verification` together correspond to A3's `action_result`.

**More materially:** §30.7 characterises the gap as *naming*. It is **structural**. Roughly
two-thirds of A3 §6.2's state vocabulary has no implementation at all — `case_ref`,
`problem_statement`, `understanding_confidence`, `ambiguity_type`, `clarify_iterations`,
`pending_question`, `resolution_type`, `resolution_ref`, `match_confidence`, `sop_document`,
`params_status`, `tool_binding`, `approval_request_id`, `user_profile`, `recalled_incidents`,
`escalation_reason` — and six of the fourteen governed areas in §30.2 have no implementation surface
to govern. Recorded as a conformance finding; **not corrected**, per §30.7's own instruction.

### 10.3 Interrupts, resume, checkpoint

Three interrupts, all LangGraph `interrupt()` over the HTTP/SSE turn: clarification
(`conversation.py:66-72`, unreachable node), consent (`interrupts.py:57-64`), approval
(`interrupts.py:99-106`). The consent and approval nodes **discard the resume return value by
design** and re-read `deps.consents`/`deps.approvals`; no decision → re-suspend. That is a sound
fail-closed choice and matches A3's intent that a transcript value is never the authority.

**Resume is not implemented end to end.** `resume_worker.py` treats `kind` as a routing hint,
dead-letters every non-sample kind via `refuse_unhandled_kind`, and its `main()` raises
`NotImplementedError` (`:144`). No `Command(resume=...)` exists anywhere. Live resume is equally
unavailable: the staff verdict route is 501.

Checkpointing conforms (see §9). Thread key `"{tid}:{oid}:{sid}"` (`threads.py:32-44`) matches
ADR-008's `tenant:user:session`.

### 10.4 Rule-vs-implementation contradictions

| `30-langgraph.md` statement | Finding |
|---|---|
| §30.7 surface table | Accurate; `nodes/clarification_interrupt.py` is not mentioned |
| §30.7 "Resume servicing also runs … `ragcore/workers/resume_worker.py`" | Path correct, but phrasing implies a working resume path; there is none |
| §30.7 recorded deviation | Mapping error + understates the gap (see §10.2) |
| §30.3 "execution re-reads authoritative durable state" | **Contradicted by `execute`** (§6) |
| §30.3 "No side effect occurs directly from an agent node" | **Not contradicted** |

No file in the graph package instructs behavior contrary to the rule's *procedure*. The
contradictions are between what the rule *records as the state of the implementation* and what the
implementation is.

---

## 11. ADR Governance Validation

| Check | Result |
|---|---|
| Sequence `0001`–`0009` | **Complete, no gaps, no duplicates.** Next number unambiguously **`0010`** |
| Structural validity | All nine pass H5 offline |
| Dialect | All use `# NNNN. <title>` + `- **Status:** …`; `0009` uses `## Decision` rather than `## Decision Outcome` — rule 70.5 permits both |
| Status values | Three records append qualifiers to `Accepted` (0001 "amended in part by 0007", 0003 "extended by", 0005 "relocated by"). Outside the strict 70.5 vocabulary but accepted by the guard's regex. Factual note, not a failure |
| H5 behavior | Checks 4-digit kebab filename, duplicate number, sequence continuation, status-field presence, `Context`/`Decision`/`Consequences` by prefix match, title-carries-number, and warns on edits to existing records. **Never writes a file, never marks an ADR accepted.** `adr_structure_guard.py:244` — `return 0  # …the governance gate is still the human's` |
| H5 limits | Content checks apply only to whole-file `Write` calls; an Edit or Bash heredoc gets filename checks only — but still **blocks** (`text is None` forces exit 2). Offline `--check` never prints the historical-record notice (`:263`). Neither is a safety failure |
| A3 inline ADR-001…ADR-012 | **Present** (`RagAgent-Architecture-final.md:141-251`). **Numbering spaces cleanly separated by digit width** — A3 uses three digits exclusively, `docs/adr/` four; zero cross-contamination in any governance file. OQ-5 remains open by design |
| DB/LangGraph → ADR escalation | **Correct** — `adr-author/SKILL.md:19-20, 37-41, 112-117`, including "checkpoint persistence → the DB ordering wins (rule 50.6 / 30.8)" |

### 11.1 One ambiguity in the adr-author skill

`adr-author/SKILL.md:244` instructs:

> Record the acceptance the human gave — status `Accepted`, with the date — because the human said
> it, never because the code is ready.

This is the only instruction in the repository telling Claude to write `Accepted`. It sits in tension
with the skill's own prohibition list (`:270`) and with `70-adr.md:236-238` ("Claude … does not
change a status from `Proposed` to `Accepted`"). It **is** reconcilable — 70.5 permits "the recording
of an acceptance a human has explicitly given in this session", and the step is gated behind an
explicit wait at Step 7. Flagged as a wording ambiguity worth tightening, **not** as a governance
hole. Non-blocking.

### 11.2 `docs/adr/README.md` — reported, not resolved

The index is **accurate for all nine records** — numbers, filenames, titles and statuses all match,
including amendment qualifiers. The mismatch is of a different kind: **the index still derives its
authority from retired sources.**

| Line | Text | Problem |
|---|---|---|
| `:4` | "numbered sequentially, with a status field (**constitution Principle X**)" | Cites the retired constitution |
| `:5`, `:50` | grounds the record set in divergence from `Synthia-Platform-Specification.md` | `70-adr.md:19` names this as carrying no authority |
| `:51`, `:53-54` | "**constitution Principle V**", "**Principle VI**", "**plan Stage 4**" | Retired sources |
| `:30`, `:31`, `:37` | cites `spec.md §Dependencies`, task ids `T117`, `T227a` | Spec Kit task ids |
| `:45`, `:48-54` | "Number it sequentially" without stating `0010`; trigger list is the **old four-item Spec Kit list** | A reader following the README alone would not learn that a §30.4 LangGraph change or a §50.5 DB change requires an ADR |

**Deliberately not resolved.** Per the Phase 7 instruction, repointing the ADR index is *governance
remediation*, not conformance validation. It is listed as remediation item R-7 (§19) and requires
the human decision at §17 D-6. Historical ADRs `0001`–`0009` were not touched.

---

## 12. Functional Knowledge Validation

`docs/functional/implemented.md` was validated against implementation. **It was not altered.**

| Check | Result |
|---|---|
| Revision metadata | States `de27d81`, HEAD is `2febbb0`. **One commit behind but substantively accurate**: `2febbb0` touched exactly three files — `90-functional-knowledge.md`, `functional-update/SKILL.md` and `implemented.md` itself — and `git diff de27d81 2febbb0 -- ragcore/ integrations/ dotnet/ apps/ build/` is **empty**. No functional claim is stale on that account |
| Branch named | Says `speckit-to-claude`; the document now also lives on `phase-7-validation`. Cosmetic |
| Classification labels | All six defined verbatim (`:30-39`) and used consistently |
| Production-reachable vs test-only | **Rigorously separated** — this is the document's strongest property. `:281-292` makes it the load-bearing fact of the whole graph section, and the same discipline is applied to `ExecutionLeg`, `SafeModel`, hybrid/rerank and ServiceNow |
| Prohibited content | **None.** Grep for `will support\|should support\|planned\|future\|to be implemented\|roadmap\|acceptance criteria\|user stor\|requirement` returns **two hits, both in the document's own disclaimer** (`:10-11`, "Not a requirements document… not a roadmap"). Both fall inside the §90.4 exception |
| Conformance findings | §21 records four divergences in exactly the neutral shape §90.7 prescribes |
| Evidence spot-check | **14 substantive claims checked against source. All VERIFIED.** None UNSUPPORTED, CONTRADICTED or stale in substance |
| Path references | 103 cited paths resolved; **two unresolvable, and the document itself reports both as missing** (`tests/unit/test_run_host.py`, `tests/e2e/test_sample_flows_are_inert.py`) |
| `specs/**` or `.specify/**` references | **One**, at `:12`, and it is a disclaimer of non-use |

**Defects — all minor, all non-blocking:** three line-number drifts (`sessions.py:85`→`:94`;
`answers.py:77`→`:79`; `fixtures.py:195`→`:196`) and the branch-name/revision cosmetics above.

**No correction was made.** Per the Phase 7 instruction, reporting was preferred; none of these
defects impairs the validation's meaningfulness. Listed as R-8 (§19).

`implemented.md` is the healthiest artifact in the migration. **SK-9 is met.**

---

## 13. Hook / Mechanical Enforcement Validation

### 13.1 Executed gate results

Every result below was **observed in this session**. Nothing unrun is called passed.

| Gate | Command | Result |
|---|---|---|
| Governance guards | `python .claude/hooks/test_guards.py` | **188/188 checks passed** |
| .NET build | `dotnet build -warnaserror` | **exit 0** |
| .NET tests | `dotnet test` | **exit 0** |
| RagCore lint/format/types | `uv run ruff check .` / `ruff format --check .` / `mypy` | **all exit 0** |
| RagCore tests | `uv run pytest -q` | **1301 passed** |
| RagCore integration (Docker) | `uv run pytest -q -m integration` | **159 passed, 1142 deselected** |
| Integrations lint/format/types | ruff / ruff format / mypy | **all exit 0** (67 source files) |
| Integrations tests | `uv run pytest -q` | **155 passed** |
| Boundary check | `bash build/scripts/check-boundaries.sh` | **exit 0** |
| Boundary guard self-test | `verify-boundary-guard.sh` | **passed** |
| Architecture guard self-test | `verify-architecture-guards.sh` | **passed** — every planted violation class rejected, clean tree accepted |
| Web lint/format/types | `npx eslint .` / `prettier --check .` / `tsc -b --force` | **all clean, exit 0** |
| Web build | `npm run build` | **exit 0** — bundle generated, initial total 296.60 kB |
| Web unit tests | `npm test` | **9 passed, 0 failed** (3 suites) |

Docker was available, so the migration/persistence suites were **actually executed** rather than
classified unverified. This raises Phase 6's "unverified" DB coverage to verified.

**A note on one false alarm, recorded so it is not rediscovered.** An initial `npx tsc -b` run
reported 92 errors. A clean `tsc -b --force` after deleting `.tsbuildinfo` returns **exit 0**. The
92 errors were an artifact of running tsc concurrently with parallel background jobs, not a real
failure. **The web TypeScript build is clean.**

### 13.2 Not executed — classified UNVERIFIED, not passing

| Gate | Why not run |
|---|---|
| Web a11y + CSP (Playwright/Chromium) | Requires `npx playwright install --with-deps chromium`; not installed here |
| `apps/desktop` Electron suite | Not run |
| `contracts.yml` full pipeline | Requires the multi-deployable emit/diff/publish sequence in CI |
| `security.yml` (gitleaks, dependency audit) | Not run |
| `edge.yml`, `images.yml`, `base-image-digests.yml` | Not run |
| Node version parity | CI pins Node 22; this audit used Node 24 |

### 13.3 BLOCKER B-3 — hooks do not fire inside a git worktree

**This is the most serious mechanical-enforcement finding, and it was demonstrated live.**

While auditing, an `Edit` to `ragcore/src/ragcore/graph/builder.py` inside the worktree was
**not blocked** by H3 — it failed only on a string mismatch. Root cause is in
`_guardlib.normalize()`:

```python
def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())

def normalize(path: str) -> str:
    cleaned = path.strip()....replace("\\", "/")
    root = project_dir().replace("\\", "/").rstrip("/")
    if root and cleaned.lower().startswith(root.lower() + "/"):
        cleaned = cleaned[len(root) + 1 :]
```

`normalize()` strips only the `CLAUDE_PROJECT_DIR` prefix. When work happens in a worktree under
`.claude/worktrees/<name>/`, `CLAUDE_PROJECT_DIR` remains the main checkout, so an absolute worktree
path normalizes to `.claude/worktrees/<name>/ragcore/src/ragcore/graph/builder.py` — which matches
**no** governed prefix. The guard reports "not governed" and exits 0.

Reproduction (run in this session; exit 2 = blocked, exit 0 = allowed):

| Guard | `CLAUDE_PROJECT_DIR` | Path form | Result |
|---|---|---|---|
| H3 | main checkout | relative | **BLOCKED (2)** |
| H3 | main checkout | absolute, main checkout | **BLOCKED (2)** |
| H3 | main checkout | absolute, **worktree** (fwd slashes) | **ALLOWED (0)** |
| H3 | main checkout | absolute, **worktree** (backslashes) | **ALLOWED (0)** |
| H3 | worktree | absolute, worktree | BLOCKED (2) |
| H3 | worktree | absolute, main checkout | ALLOWED (0) |
| H2 | main checkout | relative | **BLOCKED (2)** |
| H2 | main checkout | absolute, **worktree** | **ALLOWED (0)** |

**Impact.** This repository's own background-agent guidance directs agents to work in a worktree
under `.claude/worktrees/` before making changes. In exactly that configuration, **H2 and H3 are
inert.** A migration or graph change made from a worktree passes the DB and LangGraph gates
silently. H5 is affected identically for `docs/adr/`.

**Classification:** `MISSING` mechanical enforcement in the worktree configuration. **Severity:
High — this is a governance bypass, not a style defect.**

**Required action:** fix `normalize()` to resolve a worktree path to its repository-relative form
(and/or add a worktree-path regression case to `test_guards.py`, which currently has no such case —
its 188 checks all pass while the bypass exists). **Not fixed in Phase 7** (§23 no-remediation rule);
listed as R-1 (§19), and it is a prerequisite for SK-10.

### 13.4 Other mechanical-enforcement gaps

| Finding | Evidence | Classification |
|---|---|---|
| **H2 does not cover the Integrations persistence surface** | `db_migration_guard.py:32-35` lists only `ragcore/migrations/` and `ragcore/src/ragcore/persistence/`. But `50-database.md:98` names ORM persistence models as a DB change, and §50.7 records that revisions `0020`–`0025` are the integrations schema. An edit to `integrations/src/integrations/persistence/**` (5 files) **does not fire the DB gate** | `MISSING` — Medium |
| `MultiEdit` in the settings matcher | `MultiEdit` does not appear in current Claude Code documentation. Harmless (an unmatched alternative never fires) but stale | Non-blocking |
| `test_guards.py` is not wired into CI | `grep test_guards` across `.github/` and `build/` → nothing. It is invoked by hand per rule 70.8 | Non-blocking, but means the governance self-check is not gated |
| Hooks run **in parallel**, most-restrictive-wins | Documented Claude Code behavior; the three-guard registration is correct | Confirmed sound |
| `python3` on Windows | Resolves via the pyenv-win shim (`/c/Users/.../shims/python3`) and the guards execute correctly. Portability depends on the shim being present | Non-blocking, environment-dependent |

### 13.5 False positives / bypasses

No false positive was found: the guards are narrow path guards and correctly ignore heredoc bodies,
grep patterns and `__pycache__`. The only bypass found is B-3. The guards correctly refrain from
semantic judgement, exactly as rules 30.10/50.9/70.9 state — no brittle semantic check was added.

---

## 14. Spec Kit Dependency Audit

**Nothing was removed.** This is the retirement dependency list.

**690 hits across 253 tracked files** outside the Spec Kit asset tree. Token split: `constitution`
443 + `Constitution` 61 + `CONSTITUTION` 3, `speckit` 341, `.specify` 87, `specs/` 50,
`Synthia-Platform-Specification` 25, `Spec Kit` 23, `spec-kit` 22, `SPECIFY_` 10.

### 14.1 The asset tree

| Tree | Size | Contents |
|---|---|---|
| `.specify/` | 20 files, 193 KB | `init-options.json`, `integration.json`, 2 integration manifests, **`memory/constitution.md` (968 lines)**, 6 PowerShell scripts, 5 templates, 2 workflow files |
| `specs/001-platform-scaffold/` | 24 files, 708 KB | spec, plan, tasks, data-model, research, quickstart, 2 freeze docs, 4 stage-notes, 3 checklists, 9 contracts |
| `Synthia-Platform-Specification.md` | 206 KB | root; 25 references |

**Constitution status — worth flagging.** Its own footer reads `**Version**: 4.0.0 | **Ratified**:
2026-09-15 | **Last Amended**: 2026-09-18`, with a SYNC IMPACT REPORT and an open deviation D-01. **It
carries no retirement, superseded or deprecated marker.** The only place it is called retired is
`.claude/rules/70-adr.md:20`. A reader opening the file sees an actively amended governance document.

Note: `.specify/extensions.yml` and `.specify/feature.json` — referenced by all 10 skills — **do not
exist** in the tree.

### 14.2 Classification summary

| Classification | Count | Principal instances |
|---|---|---|
| `RUNTIME_DEPENDENCY` | **10** | The 10 `speckit-*` skills — each invokes `.specify/scripts/powershell/*.ps1` and reads `.specify/memory/constitution.md` |
| `GOVERNANCE_DEPENDENCY` | **8** | `test_guards.py:522-524`; `70-adr.md:19-20`; `90-functional-knowledge.md:52-53`; `adr-author/SKILL.md:100` |
| `BUILD_CI_DEPENDENCY` | **1** | `.dockerignore:86` — an *exclusion* pattern; becomes a harmless no-op after deletion |
| `DOCUMENTATION_REFERENCE` | ~40 | `README.md:16-19,72,146,224,235`; `.serena/memories/*`; `docs/current-implementation/file-map.md`; **`docs/architecture/integrations-service-delta.md` (18 hits)** |
| `HISTORICAL_REFERENCE` | ~60 | `docs/adr/0001`–`0009` + README; `docs/migration/**` |
| `DEAD_STALE_REFERENCE` | ~570 | ~430 source/test/Docker/ESLint comments citing "constitution Principle N"; 10 build-config comments; worker `NotImplementedError` message strings |

### 14.3 What would actually break

**Would BREAK:**

| What | Trigger | Evidence |
|---|---|---|
| The 10 `speckit-*` skills | **Deleting `.specify/`** | Each runs `.specify/scripts/powershell/{check-prerequisites,setup-plan,setup-tasks,resolve-template}.ps1` at its first step. A skill-invocation failure, not a build or CI failure |
| `.claude/hooks/test_guards.py` | **Deleting any `speckit-*` skill** | `:524` — `check("Spec Kit skills still present", len(speckit) == 10)`. Hard-codes `== 10`. **This is the only executable Spec Kit assertion in the repository**, and Phase 2 §14 does not name it. Blast radius is the governance self-check, since `test_guards.py` is not in any workflow |

**Would NOT break — dead links and dead comments only:**

- **Every .NET build path.** No MSBuild `Import`/`Include` references either tree; there are no
  `.targets` files at all. `Directory.Build.props`, `Directory.Packages.props` and `.editorconfig`
  hits are comments and one decorative `Label=`.
- **Every Python build/CI path.** Both `pyproject.toml` files and `alembic.ini` reference the
  constitution only in `#` comments.
- **All 12 GitHub workflows.** No `paths:` trigger, checkout or `run:` step touches either tree — all
  hits are header comments.
- **The entire contract pipeline.** It emits into and diffs against `build/contracts/**`;
  `specs/001-platform-scaffold/contracts/` is never read.
- **`ragcore/tests/contracts/test_api_surface.py`** — its docstring cites `specs/…` but the code
  resolves `parents[3]` + `build/contracts/`. It passes with `specs/` deleted.
- All seven worker `NotImplementedError` strings; `build/policy/openapi-disclosure.json:80`;
  `build/infra/apim/apis.json:8`; `build/infra/messaging/queues.json:5` — string values, not paths.

### 14.4 Two items Phase 2 §14 does not name

1. **`test_guards.py:523-524` hard-codes `len(speckit) == 10`** — removing the skills fails the
   governance self-check. Must be updated in the same change as SK-12.
2. **`docs/architecture/integrations-service-delta.md` (18 hits)** is an active architecture-directory
   document whose entire premise is reconciling `.specify/memory/constitution.md` v3.1.0 against
   `specs/001-platform-scaffold/*`. It is non-authoritative per rules 70/90, but it is **not** in
   `docs/adr/` or `docs/migration/`, so the historical-preservation carve-out does not cover it.
   Disposition needed (§17, D-5).

### 14.5 Actively misleading after deletion

Distinct from merely dead: **`.serena/memories/*`** instructs a future agent to read
`.specify/memory/constitution.md` and to edit `specs/001-platform-scaffold/contracts/` on every
contract change (`core.md:6-8,29-30`; `task_completion.md:3,14,16`). After deletion these become
instructions pointing at nothing. `README.md:17-19,235` become broken front-page links.

---

## 15. Retirement Prerequisite Matrix

| ID | Prerequisite | Status | Evidence | Blocker reason | Required action | Human decision? |
|---|---|---|---|---|---|---|
| **SK-1** | All retained YAML rules migrated | **NOT MET** | §4.2 — 122/128 destinations absent; 2/128 genuinely covered | The eight baseline rule files were never written | Author `10-principles`, `20-dotnet`, `21-python`, `40-testing`, `80-security-ops` (+ `00-authority`, `60-architecture-gates`) | No — execution |
| **SK-2** | Explicit `<baseline-rules>` completely migrated | **BLOCKED** | §5.1 — block not supplied in Phase 2 **or** Phase 7 | Required input never delivered | Supply the block, or confirm in writing that none exists | **YES (D-1)** |
| **SK-3** | Coverage validated | **NOT MET** | §4 | Cannot validate coverage of a baseline that is 95% unwritten and an explicit block that is absent | Complete SK-1 and SK-2, then re-run coverage | No, after D-1 |
| **SK-4** | Claude governance exists | **PARTIAL** | §3 | 4 of 12 anticipated rule files exist; no `CLAUDE.md` | Complete SK-1; decide on `CLAUDE.md` | Partly (D-7) |
| **SK-5** | Testing governance exists | **NOT MET** | §3.2 | `40-testing.md` absent; testing obligations exist only inside 30/50/70/90 | Author `40-testing.md` | No |
| **SK-6** | DB governance exists | **MET** | `50-database.md` + H2 + `db-change` skill; §9 — all DB gates executed and passed | — | — | No |
| **SK-7** | LangGraph governance exists | **MET** | `30-langgraph.md` + H3 + `langgraph-change` skill; §10 | — | — | No |
| **SK-8** | ADR governance exists | **MET** | `70-adr.md` + H5 + `adr-author` skill; §11. Sequence sound, next = `0010` | — | — | No |
| **SK-9** | Functional knowledge exists and is current | **MET** | §12 — 14/14 claims verified, no prohibited content, classifications sound | — | (optional R-8 tidy) | No |
| **SK-10** | Governance validation passed | **NOT MET** | §13.3 — H2/H3/H5 inert inside a worktree; `test_guards.py` has no worktree case | A demonstrated governance bypass | Fix `_guardlib.normalize()`; add a worktree regression test; extend H2 to integrations persistence | No — execution |
| **SK-11** | Constitution references repointed/removed | **NOT MET** | §14.2 — ~440 constitution citations, incl. 10 in live build config (`Directory.Build.props:4,34`, `Directory.Packages.props:4,31`, `.editorconfig:1,79,85,97`, `ragcore/pyproject.toml:65,73,82,95`) | Enforcement config cites a retired authority | Repoint comments to `.claude/rules/` once those rules exist — i.e. **after SK-1** | No |
| **SK-12** | speckit skills disposition decided | **UNDECIDED** | §14.3 — 10 skills, all RUNTIME_DEPENDENCY; `test_guards.py:524` asserts `== 10` | Retain / archive / delete not decided | Decide; update `test_guards.py:524` in the same change | **YES (D-5)** |
| **SK-13** | Platform specification disposition decided | **UNDECIDED** | `Synthia-Platform-Specification.md`, 206 KB, 25 refs; OQ-3 | Not decided | Decide retain/archive/delete | **YES (D-5)** |
| **SK-14** | `specs/**` disposition decided | **UNDECIDED** | 24 files, 708 KB; nothing executable reads them | Not decided | Decide | **YES (D-5)** |
| **SK-15** *(new)* | Worktree-safe guard normalization | **NOT MET** | §13.3 | Same as SK-10; called out separately because it is a code fix with a regression test, not a policy act | Fix + test | No |
| **SK-16** *(new)* | TS/Angular/Electron governance scope decided | **UNDECIDED** | §5.3 — OQ-2 | `apps/web` + `apps/desktop` have no governance text | Decide principles-only / separate baseline / ungoverned | **YES (D-2)** |
| **SK-17** *(new)* | `.serena/**` and `README.md` repointed | **NOT MET** | §14.5 | Would actively misdirect agents after deletion | Repoint in the removal change | No |
| **SK-18** *(new)* | Spec Kit path removed from published contract | **NOT MET** | §8 — `customer.v1.openapi.json:435` | A Spec Kit path ships in a wire artifact | Edit `sample_flows.py:119`, re-emit contracts | No |
| **SK-19** *(new)* | `integrations-service-delta.md` disposition | **UNDECIDED** | §14.4 | Active doc built entirely on Spec Kit sources; outside the historical carve-out | Decide | **YES (D-5)** |

**Met: 4 of 19 (SK-6, SK-7, SK-8, SK-9).**

No prerequisite was marked complete merely because an intended file exists.

---

## 16. Blocking Issues

Each carries: finding · authority · evidence · impact · classification · required action.

### BLOCKER B-1 — The engineering baseline was mapped but not migrated

- **Finding.** 122 of 128 baseline rules point at `.claude/rules/` files that do not exist. Two are
  genuinely covered. Four of the six that reached an existing file were dropped in transit.
- **Source/authority.** `principles.yaml`, `python.yaml`, `python_lang.yaml`, `dotnet.yaml`,
  `dotnet_lang.yaml`; destinations per `docs/migration/phase-2-coverage-matrix.md`.
- **Evidence.** §4.2, §4.3. `git ls-files .claude/rules/` returns four files; the matrix names seven
  destinations. `grep -rn 'principles#\|lang/dotnet\|P-DN\|P-PY'` over `.claude/` → **0 matches**.
- **Impact.** The engineering baseline — the bulk of what Spec Kit governed — has no Claude-facing
  representation. 83 rules survive only as CI gates that can reject a change for reasons Claude was
  never told. 39 rules are unguarded entirely. Retiring Spec Kit now would delete the only written
  form of rules that were never rewritten.
- **Classification.** `MISSING` — SK-1, SK-3, SK-4, SK-5.
- **Required action.** Author the missing rule files from the five YAMLs, preserving scope and
  strictness; re-run the coverage validation.

### BLOCKER B-2 — The `<baseline-rules>` block was not supplied to Phase 7 either

- **Finding.** The block named as an authoritative Phase 7 input was absent from the Phase 7
  execution context, as it was from Phase 2's.
- **Source/authority.** The Phase 7 migration instructions, §3.
- **Evidence.** §5.1. No `<baseline-rules>` block appears anywhere in this session's inputs. Not
  reconstructed from `.specify/**`, the constitution, or implementation, per the source policy.
- **Impact.** SK-2 cannot be evaluated. Per the migration-safety rule that no supplied rule may be
  silently dropped, coverage cannot be declared complete in either direction.
- **Classification.** Blocking validation-input problem.
- **Required action.** Supply the block, **or** confirm in writing that none exists and that the five
  YAMLs are the entire engineering baseline. **Human decision D-1.**

### BLOCKER B-3 — Governance hooks are inert inside a git worktree

- **Finding.** H2, H3 and H5 allow writes to governed paths when the edit is made from
  `.claude/worktrees/**` and `CLAUDE_PROJECT_DIR` is the main checkout.
- **Source/authority.** `.claude/rules/30-langgraph.md` §30.10, `50-database.md` §50.9,
  `70-adr.md` §70.9 — each states its hook fires deterministically on the governed surface.
- **Evidence.** §13.3. Demonstrated live: an `Edit` to `ragcore/src/ragcore/graph/builder.py` in the
  worktree was not blocked. Reproduced deterministically across eight path/env combinations. Root
  cause: `_guardlib.normalize()` strips only the `CLAUDE_PROJECT_DIR` prefix.
- **Impact.** This repository's own background-agent guidance directs agents into a worktree before
  editing. In exactly that configuration the DB, LangGraph and ADR gates do not fire. `test_guards.py`
  passes 188/188 while the bypass exists, because it has no worktree case.
- **Classification.** `MISSING` mechanical enforcement — **High severity governance bypass.**
- **Required action.** Make `normalize()` worktree-aware; add a worktree regression case to
  `test_guards.py`. Prerequisite for SK-10/SK-15. **Not fixed in Phase 7** (no-remediation rule).

### BLOCKER B-4 — TypeScript / Angular / Electron governance scope is undecided

- **Finding.** `apps/web` (7 Angular projects) and `apps/desktop` (Electron) have no governance text
  of any kind, and the intended scope was never decided.
- **Source/authority.** The five YAMLs (none contains a TS/Angular/Electron rule);
  `phase-2-authority-model.md:182`, OQ-2.
- **Evidence.** §5.3. `22-web-typescript.md` does not exist. Grep across all five YAMLs returns one
  false positive.
- **Impact.** Two of the platform's four surfaces are ungoverned, while carrying strong CI gates
  (eslint, prettier, tsc, a11y, CSP, Electron security) that no baseline explains.
- **Classification.** `MISSING` — SK-16.
- **Required action.** Decide: principles-only, separately supplied baseline, or deliberately
  ungoverned. **Human decision D-2.** No TS rules were authored in Phase 7.

---

## 17. Human Decisions Required

Phase 7 made none of these.

| ID | Decision | Why it is human | Bears on |
|---|---|---|---|
| **D-1** | Supply the `<baseline-rules>` block, or confirm in writing that none exists and the five YAMLs are the complete baseline | Changes what the engineering baseline *is*. Cannot be assumed either way | B-2, SK-2, SK-3 |
| **D-2** | TS/Angular/Electron governance scope — principles-only, separate baseline, or deliberately ungoverned | Changing the baseline's reach is a baseline change (`70-adr.md` §70.2 B) | B-4, SK-16 |
| **D-3** | Whether to accept, or remediate, the A1 §12.2 immutability deviation — approval requirement, `approved_by_oid`, `approved_at` not protected at the DB permission boundary | Remediation is an architecture change requiring an **ADR** under `70-adr.md` §70.2 D(1)/D(3), not merely approval | §9.1 |
| **D-4** | Whether to accept each A3 conformance deviation (execution re-read, signed/idempotent execution, two-index retrieval, typed resolution, clarify loop, memory, tool binding, eval gates) as expected scaffold state, or schedule them | Accepting or closing an architecture deviation is an architecture decision | §6, §10 |
| **D-5** | Disposition — retain / archive / delete — for: the 10 `speckit-*` skills; `Synthia-Platform-Specification.md`; `specs/**`; `.specify/**`; `docs/architecture/integrations-service-delta.md` | Retaining or destroying historical documents | SK-12, SK-13, SK-14, SK-19 |
| **D-6** | Whether repointing `docs/adr/README.md` off the constitution and the platform specification is authorized as governance remediation | Phase 7 is conformance validation; the instructions require this be classified deliberately, not auto-resolved | §11.2, R-7 |
| **D-7** | Whether `CLAUDE.md` and `.claude/skills/architecture-conformance/SKILL.md` are required for the intended governance model | Defines the intended model, not merely its implementation | §3.3 |
| **D-8** | Whether the `CA2007 = none` relaxation (`lang/dotnet#DN8`) is an accepted baseline change | A deliberate baseline relaxation with no ADR is itself an ADR trigger (`70-adr.md` §70.2 B(1)) | §4.5 |

---

## 18. Non-blocking Findings

| # | Finding | Evidence | Classification |
|---|---|---|---|
| N-1 | H2 does not cover `integrations/src/integrations/persistence/**` (5 files), though `50-database.md` §50.7 records `0020`–`0025` as the integrations schema | `db_migration_guard.py:32-35` | `MISSING` — Medium |
| N-2 | `MultiEdit` in the settings matcher is not a documented current tool | `.claude/settings.json` | Stale, harmless |
| N-3 | `test_guards.py` is not wired into any CI workflow | `grep test_guards` over `.github/` → nothing | Governance self-check ungated |
| N-4 | `adr-author/SKILL.md:244` instructs writing `Accepted`, in tension with its own `:270` and `70-adr.md:236` | §11.1 | Wording ambiguity; reconcilable |
| N-5 | Three ADR statuses carry qualifiers outside the 70.5 vocabulary (0001, 0003, 0005) | §11 | Factual note |
| N-6 | `docs/adr/README.md` trigger list is the old four-item Spec Kit list; never states the next number is `0010` | `README.md:45,48-54` | Stale guidance |
| N-7 | Three line-number drifts in `implemented.md` | §12 | Cosmetic |
| N-8 | `implemented.md` names branch `speckit-to-claude`; revision `de27d81` is one commit behind HEAD but substantively accurate | §12 | Cosmetic |
| N-9 | `model/safety.py:16` asserts a composition binding that does not exist | §7.4 | Docstring/implementation defect |
| N-10 | `host.py:91` and `sessions.py:246` cite `tests/unit/test_run_host.py`, which does not exist | §7.6 | Docstring defect (rule 90.2) |
| N-11 | `graph/nodes/clarification_interrupt.py` is an orphan module, registered nowhere | §10.1 | Dead code |
| N-12 | Spec Kit path shipped in a published contract (`customer.v1.openapi.json:435`) | §8 | SK-18 |
| N-13 | `.serena/memories/*` would actively misdirect agents after Spec Kit deletion | §14.5 | SK-17 |
| N-14 | The constitution carries no retirement marker of its own; only `70-adr.md:20` calls it retired | §14.1 | Discoverability risk |
| N-15 | `.specify/extensions.yml` and `.specify/feature.json`, referenced by all 10 skills, do not exist | §14.1 | Pre-existing breakage |
| N-16 | Matrix enforcement-column errors: DN8, DN31, DN16 | §4.5 | Corrected in this report |
| N-17 | Web/desktop CI gates exist with no baseline behind them | §5.3 | Mirror image of §4.2 |

---

## 19. Recommended Remediation Order

Ordered by dependency, not severity. Each governed change still runs its own gate.

| # | Action | Unblocks | Gate that applies |
|---|---|---|---|
| **R-1** | Fix `_guardlib.normalize()` for worktree paths; add a worktree regression case to `test_guards.py`; extend H2 to `integrations/src/integrations/persistence/**` | SK-10, SK-15, N-1 | Governance guard tests — do it **first**, so every later change is actually gated |
| **R-2** | Obtain D-1 (the `<baseline-rules>` block, or written confirmation none exists) | SK-2, SK-3 | Human input |
| **R-3** | Obtain D-2 (TS/Angular/Electron scope) | SK-16 | Human input |
| **R-4** | Author `00-authority.md`, `10-principles.md`, `20-dotnet.md`, `21-python.md`, `40-testing.md`, `60-architecture-gates.md`, `80-security-ops.md` (+ `22-web-typescript.md` per D-2) from the five YAMLs, preserving scope and strictness; restore the four dropped rules; cite baseline IDs for traceability | SK-1, SK-3, SK-4, SK-5 | Baseline change — `70-adr.md` §70.2 B if any rule is deliberately relaxed |
| **R-5** | Decide `CLAUDE.md` (D-7); add it if adopted | SK-4 | — |
| **R-6** | Re-run the coverage validation against the now-existing destinations; correct the DN8/DN31/DN16 rows | SK-3 | — |
| **R-7** | Repoint `docs/adr/README.md` off the constitution and the platform specification, and onto `70-adr.md` §70.2's four trigger families — **only if D-6 authorizes it**. Do not touch `0001`–`0009` | N-6 | `70-adr.md` §70.6 |
| **R-8** | Correct the three line drifts and the revision/branch metadata in `implemented.md` | N-7, N-8 | `90-functional-knowledge.md` |
| **R-9** | Repoint the ~440 constitution comments in source, tests, build config and CI onto `.claude/rules/` — **after R-4**, since the targets must exist first | SK-11 | — |
| **R-10** | Fix `sample_flows.py:119`; re-emit contracts (the staleness gate will demand it) | SK-18 | `contracts.yml` |
| **R-11** | Repoint `.serena/memories/*` and `README.md:16-19,72,235` | SK-17 | — |
| **R-12** | Obtain D-5; then execute the Spec Kit removal, updating `test_guards.py:524` in the same change | SK-12, SK-13, SK-14, SK-19 | **Phase 8** |
| **R-13** | Record D-3, D-4, D-8 outcomes; raise ADRs for any accepted architecture or baseline change | §17 | `70-adr.md` §70.3 |

**R-1 genuinely belongs first.** Until the guards fire in a worktree, every remediation step above
can be performed with the DB, LangGraph and ADR gates silently inert.

---

## 20. Phase 8 Readiness

### `NOT READY FOR PHASE 8`

Spec Kit retirement is **not authorized**.

**Prerequisites met: 4 of 19** — SK-6 (DB governance), SK-7 (LangGraph governance), SK-8 (ADR
governance), SK-9 (functional knowledge).

**Blockers, precisely:**

1. **B-1 / SK-1, SK-3, SK-4, SK-5** — 122 of 128 engineering-baseline rules have no destination
   file; only 2 are genuinely covered; 4 of the 6 that reached an existing file were dropped.
   Retiring Spec Kit now would delete the only written form of rules never rewritten.
2. **B-2 / SK-2** — the explicit `<baseline-rules>` block was not supplied to Phase 2 **or** Phase 7.
   Coverage cannot be declared complete. Requires D-1.
3. **B-3 / SK-10, SK-15** — H2/H3/H5 are inert for edits made inside a git worktree, the
   configuration this repository's own agent guidance mandates. Demonstrated, reproducible.
4. **B-4 / SK-16** — TS/Angular/Electron governance scope undecided; two of four platform surfaces
   are ungoverned. Requires D-2.
5. **SK-11** — ~440 constitution references remain, including 10 in live enforcement configuration.
   Cannot be repointed until R-4 creates the targets.
6. **SK-12, SK-13, SK-14, SK-19** — disposition undecided for the speckit skills,
   `Synthia-Platform-Specification.md`, `specs/**`, `.specify/**` and
   `integrations-service-delta.md`. Requires D-5.
7. **SK-17, SK-18** — `.serena/**` and `README.md` would actively misdirect after deletion; a Spec
   Kit path ships inside a published wire contract.

**Explicitly not a basis for readiness**, though all are true: every executable gate passes (188/188
governance checks; 1301 + 159 + 155 + 9 tests; .NET build and tests clean; the Angular build and
lint, format and type checks clean across all stacks; boundary and architecture guard self-tests
pass); the governance files
that exist are well-built; the Spec Kit files are untouched. None of that substitutes for an
unmigrated baseline, a missing input, or a guard that does not fire.

**Phase 8 becomes authorizable when:** R-1 lands and is tested; D-1, D-2 and D-5 are answered; R-4
completes and R-6 re-validates coverage; SK-11, SK-17 and SK-18 are cleared. D-3, D-4, D-6, D-7 and
D-8 should be recorded but do not block retirement, provided each accepted deviation is recorded
where its rule requires.

---

*Produced by Phase 7 validation at revision `2febbb0151d524de1c36b91f4d4fbe007d8a857c`. No
application source, test, migration, schema, contract, architecture document, ADR, CI definition or
Spec Kit asset was modified.*
