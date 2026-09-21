# Phase 15 — final Spec Kit reconciliation

**Kind: record (Diátaxis *explanation* + *reference*).** This file records what Phase 15 did and
what it found. It is a migration record: **it is not authority**, it authorizes nothing, and it does
not amend `.claude/rules/**`, A1, A2 or A3.

**Phase 15 deleted nothing.** `.specify/**` and `specs/**` are byte-for-byte as Phase 14 left them.

---

## 1. Starting repository state

| Check | Result |
|---|---|
| Branch | `speckit-to-claude`, clean working tree |
| Phase 14 commit present | **yes** — `a2ec80a` *docs(governance): migrate the testing baseline out of the constitution (phase 14)* is `HEAD` |
| `docs/adr/0010-frontend-engineering-baseline.md` | **Accepted** |
| `docs/adr/0011-required-test-categories-baseline.md` | **Accepted** |
| Phase 14 testing baseline exists | **yes** — `.claude/rules/40-testing.md` §40.8, §40.9, §40.10 |
| Phase 13 record exists | **yes** — `docs/migration/phase-13-spec-kit-content-reconciliation.md` |
| Phase 14 record exists | **yes** — `docs/migration/phase-14-testing-baseline-migration.md` |
| `.specify/**` and `specs/**` unchanged | **yes** — last commit touching either is `da6f439`, which predates Phase 12 |

Phase 15 was executed in a git worktree branched from `a2ec80a` (`phase-15-final-reconciliation`),
so the Phase 14 history is carried, not re-derived.

## 2. Historical correction to the Phase 13 record

`docs/migration/phase-13-spec-kit-content-reconciliation.md` line 623 read
`§Required test categories (16)`. The constitution's table holds **fifteen** rows. Corrected to
`(15)`.

**That is the only change made to the Phase 13 record.** Nothing else in it was rewritten to read
as though it had been authored after Phase 14; where Phase 13 records B13-2 and B13-3 as open, they
are left recording that, because they *were* open when it was written.

## 3. Phase 14 validation — independently re-derived from the constitution

Read from `.specify/memory/constitution.md` §Required test categories / §Which change requires
which category / §Coverage and compared against `.claude/rules/40-testing.md`:

| Obligation | Source | `40-testing.md` | Verdict |
|---|---|---|---|
| Required test categories | 15 rows | TC-01…TC-15, §40.8 | **faithful** — same names, same *Proves* text |
| Change→category matrix | 12 rows | CM-01…CM-12, §40.9 | **faithful** — same rows, same order |
| Unit owed by every change | stated | stated, §40.9 | **present** |
| Security/isolation fix owed a failing-then-passing test | stated | §40.8 and CM-12 | **present** |
| Coverage prohibition (no threshold gates a merge) | stated | §40.10 | **present, and strengthened** — lifting it now needs an accepted ADR, not merely an amendment |
| Recorded hard-failure exception (the D-01 pair) | stated | §40.10 | **present**, with the "no weaker substitute test" prohibition kept verbatim in force |
| Frontend journey row | "Frontend accessibility" | CM-11 **points at** `23-angular.md` FE-NG-5 / FE-NG-6 | **correct** — pointed, not duplicated (`00-authority.md` §00.5) |

One deliberate re-anchoring: TC-14 Security proves *"the prohibitions stated by the baseline and the
architecture are actually unreachable"* where the source said *"the prohibitions in this document"*.
That is the migration removing a self-reference to a non-authoritative document, not a change of
requirement.

**D-11-2 is fully represented in `.claude/rules/40-testing.md`.** `40-testing.md` is the sole current
testing-baseline authority for these obligations. The constitution was read as **migration input**
only; its non-authoritative status under `00-authority.md` §00.4 is unchanged by having been read.

## 4. B13-2 — the citation inventory and its disposition

Phase 13 recorded ~289 non-frontend `constitution` attributions and deferred them. Phase 15 closes
them. Every replacement was chosen from the requirement the sentence actually invokes; **no blanket
string replacement was performed**, and the multi-sense principles were split per occurrence.

### 4.1 The mapping actually used

Constitution Principles I–V and VII are **architecture** statements, so their current authority is
A1/A2/A3, not `.claude/rules/**`. Principles VI, VIII and X are engineering/governance statements and
map into the migrated baseline. Principle VI is a compound of eleven separate requirements and was
never mapped as one thing.

| Cited as | Requirement invoked | Repointed to |
|---|---|---|
| Principle I | identity derived once; identity is not transport metadata | **A1 §4.5** |
| Principle II | customer and staff authorization separate, non-hierarchical | **A1 §6** |
| Principle III | deterministic governance decides; the model only proposes | **A3 §6.3** |
| Principle III (work-item immutability) | structural control at the DB boundary | **A1 §12.2** |
| Principle III (execution validity window) | fifteen-minute window | **A3 §8.5** |
| Principle IV (tenant isolation) | no unfiltered path; isolation at every layer | **A1 §4.5, A2 P03** |
| Principle IV (secret material) | Key Vault is the sole secret source | **A2 P09** |
| Principle IV (one authority per concern) | authoritative durable store; derived/transient stores | **A2 §8.1** |
| Principle V (ports) | ports belong to the consuming module | **`10-principles.md` P-5** |
| Principle V (boundaries) | boundaries are real, not conveniences | **`10-principles.md` P-24** |
| Principle VI (cross-boundary DRY) | duplication across boundaries beats a false shared contract | **`10-principles.md` P-6** |
| Principle VI (precise types, no boolean flag) | parse at the boundary; illegal states unrepresentable | **`10-principles.md` P-20** |
| Principle VI (no speculative capability) | build nothing a requirement does not need | **`10-principles.md` P-8** |
| Principle VII | no client is a security boundary | **A2 P13** |
| Principle VIII (telemetry ≠ audit) | separate stores, separate retention | **A2 §8.1** |
| Principle VIII (no swallowed error) | every caught error handled or rethrown | **`10-principles.md` P-30** |
| Principle VIII (baggage allowlist) | explicit allowlist on the propagator | **`20-dotnet.md` BL-24** |
| Principle VIII (no claimed confirmation) | a client-reported result is a claim | **ADR-0004** |
| Principle VIII (provable by test) | the required categories | **`40-testing.md` §40.8** |
| Principle VIII (hard-failure test) | protection removed ⇒ test fails | **`40-testing.md` §40.10** |
| Principle X | decisions are recorded as ADRs | **`70-adr.md`** |
| §Required test categories | the fifteen | **`40-testing.md` §40.8** |
| §Coverage / §Quality gate | no coverage gate / the gates | **`40-testing.md` §40.10 / §40.6** |
| §.NET baseline / §.NET data access | strictness / EF conventions | **`20-dotnet.md` §20.1 / §20.4** |
| §Python baseline | toolchain, Ruff selection, mypy | **`21-python.md` §21.1** |
| §Async, §Health, §Middleware order, §Correlation, §Configuration, §Validation, §Resilience, §Idempotency, §Concurrency, §Logging, §Time, §Dependency injection | the .NET realization of each | **`20-dotnet.md`** BL-23, BL-25, BL-26, BL-27, BL-16, BL-18, BL-28, BL-29, BL-30, BL-20, DN-1, BL-2 |
| §Secrets | no credential in source; Key Vault + managed identity | **`80-security-ops.md` §80.3** |
| §Containers | probes, limits, drain, chiseled base | **`80-security-ops.md` §80.5** |
| §Model access | every model call through the AI Gateway | **A2 §9** |
| §FastAPI architecture | endpoints carry no business policy | **`10-principles.md` P-13** |
| §Observability | correlation propagated end to end | **A2 P10** |
| §Commits and versioning | Conventional Commits | **`10-principles.md` C-1** |
| §LangGraph | no second durable checkpoint store | **`50-database.md` §50.6** |
| `P-I`, `P-IV` (shorthand) | as Principles I and IV above | **A1 §4.5 / A2 §8.1** |

### 4.2 A rule is never carried to another stack by analogy

`CLAUDE.md` §4 and `00-authority.md` §00.5 forbid it, and the first mechanical pass violated it:
twelve citations in `ragcore/**` and `integrations/**` were landed on `.claude/rules/20-dotnet.md`
rule ids. **That was caught and corrected before validation.** Where a repository-wide or Python rule
states the requirement, the citation was moved there —
BL-2 → **P-26**, BL-29 → **P-21**, BL-24 → **§80.3**, BL-28 → **PY-17**, BL-20 → **PY-4**,
BL-16 → **P-27**, DN-1 → **PY-24**. Where **no** current rule states it for that stack, the citation
was **left unchanged and recorded as ambiguous** (§4.4). The same correction was applied to the
container manifests: `build/docker/containerapps/ragcore.yaml` fronts a Python service, so its probe
citation is **`80-security-ops.md` §80.5**, not the .NET BL-25.

### 4.3 Disposition by class

| Class | Count | Disposition |
|---|---|---|
| **A — current authority** ("the constitution is authoritative") | **0** | none found; `00-authority.md` §00.4 says the opposite by path |
| **B — active dependency** (execution, tooling, build, hook, test reads Spec Kit) | **0** | none found; the only executable references are the guards in `test_guards.py` that assert *absence* |
| **C — stale live citation** | **261** | **repointed** — 200 by the mechanical single-line pass, 57 by an explicit per-occurrence table, 4 at the repository root and in Serena memory |
| **D — historical record** (`docs/migration/**`) | 183 | **kept** |
| **E — historical ADR** (`docs/adr/0001…0011`, `docs/architecture/integrations-service-delta.md`) | 69 | **kept** — none creates a current instruction |
| **F — generated artifact** (`build/contracts/**`) | 3 | **source fixed, artifact regenerated** (§7) |
| **G — ambiguous** | **23** | **left unchanged and documented** (§4.4) |

Migration-input provenance lines in `.claude/rules/22-web-typescript.md`, `23-angular.md`,
`24-electron.md` and `40-testing.md` (41 occurrences) are class D by intent: each says in the same
paragraph that the constitution is **migration input and not authority**, under ADR-0010 / ADR-0011.
They are kept deliberately; removing them would erase the traceability those ADRs require.

### 4.4 The ambiguous set — 23 occurrences, left unchanged

**Fifteen are Principle IX** (§6). The other **eight** have no current home on the stack that cites
them, and inventing one would be creating a requirement, which §5 of the brief forbids:

| File | Line | Cites | Why it is ambiguous |
|---|---|---|---|
| `integrations/src/integrations/api/app.py` | 7, 87 | §Middleware order | the ordering rule is stated only in the **.NET** baseline (BL-26); no Python rule states it |
| `integrations/src/integrations/api/middleware/correlation.py` | 78 | §Middleware order | same |
| `integrations/src/integrations/api/middleware/problems.py` | 94 | §Middleware order | same |
| `integrations/src/integrations/api/middleware/problems.py` | 8 | §Validation and errors | "internal exception detail must never reach a client" is stated only as **BL-18** |
| `integrations/src/integrations/api/health.py` | 6 | §Health | "readiness must not depend on an external customer system" is stated only inside **BL-25** |
| `integrations/src/integrations/egress/http.py` | 19 | prose | "no one-off unmanaged clients" is **BL-32**; `21-python.md` PY-17 covers only the timeout half |
| `ragcore/src/ragcore/persistence/repositories.py` | 91 | prose | the generic-repository ban is **BL-14**, .NET only |

This is a **gap in the migrated baseline**, recorded under `00-authority.md` §00.7. It is not closed
here: closing it means either stating these requirements for the Python stack — an engineering-
baseline change needing an ADR under `70-adr.md` §70.2 B(6) — or deciding they are .NET-only.

## 5. Exact remaining `constitution` references

555 occurrences across 69 files, of which:

| Where | Count | Class |
|---|---|---|
| `.specify/**`, `specs/**` | 178 | inside the deletion set; untouched by Phase 15 |
| `docs/migration/**` | 183 | D — historical |
| `docs/adr/**`, `docs/architecture/integrations-service-delta.md` | 69 | E — historical |
| `.claude/rules/**`, `.claude/hooks/test_guards.py`, `CLAUDE.md`, `README.md`, `.serena/memories/core.md` | 72 | D — migration-input provenance and the guards that assert non-authority |
| **live code, build and workflow surfaces** | **23** | **G — ambiguous** (§4.4 and §6) |

**Zero class-A and zero class-B occurrences remain.**

## 6. B13-3 — Principle IX, decomposed

Principle IX (*"Scaffold Honestly; Do Not Invent Product"*) is not one requirement. Compared clause
by clause against `10-principles.md`, `22`/`23`/`24`, `60-architecture-gates.md` and
`90-functional-knowledge.md`:

| Clause | Classification | Evidence |
|---|---|---|
| **1.** "a real, buildable reference scaffold, not the complete product"; UC-01…UC-12 are placeholders and must not be invented | **Historical** | phase-specific to the original scaffold; nothing current depends on it |
| **2a.** an unsupported capability falls back to manual resolution or escalation, explicitly and visibly | **Covered** | the outcome vocabulary `{answered_sop, resolved_action, escalated, denied}` with `escalation_reason` is **A3 §6.2**; the explicit-failure half is **P-11** and **P-30** |
| **2b.** "silently degrading, **stubbing a success**, or returning a **plausible-looking fabricated result** is prohibited" | **Unique normative requirement — not covered** | P-30 governs a *caught error*; here no error is raised. `90-functional-knowledge.md` §90.4/§90.5 governs what the *record* may claim, never what the *implementation* may return |
| **3.** reference fixtures are permitted and are never product: labelled, inert, excluded from production configuration, never counted as one of UC-01…UC-12 | **Unique normative requirement — not covered** | stated in **no** `.claude/rules/**` file. Its only written homes are `.specify/memory/constitution.md` Principle IX and `specs/001-platform-scaffold/spec.md` `FR-SCOPE-004/006/007` — **both inside the deletion set** |

Clause 3 is **mechanically enforced today**: `ragcore/tests/governance/test_fixtures_excluded.py`
asserts all four properties (labelled two independent ways, inert, production-excluded by a raising
loader, never named for a use case), and `ragcore/src/ragcore/governance/fixtures.py` implements
them. So the repository enforces a requirement that, after Phase 16, **no surviving document would
state**.

```text
STOPPED. No rule was created, and no ADR was written.
```

Per §7 of the brief, the missing requirement is prepared below for an explicit human decision under
the ADR gate (`70-adr.md` §70.2 B — an engineering-baseline change). **Claude does not write the
baseline rule and does not accept the decision.**

### 6.1 Prepared for human decision — the exact missing requirement

**Source text** (`.specify/memory/constitution.md` §IX, verbatim):

> Any capability the scaffold does not support falls back to manual resolution or escalation. A
> fallback MUST be explicit and visible; silently degrading, stubbing a success, or returning a
> plausible-looking fabricated result is prohibited.
>
> **Reference fixtures are permitted, and are never product.** Inert reference operations may exist
> so that governance, consent and approval paths are demonstrable before any use case is defined.
> Each MUST be labelled a scaffold fixture, produce no real external effect, be excluded from
> production configuration, and MUST NEVER be counted as or allowed to become one of the twelve use
> cases.

**Affected scope:** repository-wide for clause 2b; `ragcore/src/ragcore/governance/fixtures.py`,
`ragcore/tests/governance/test_fixtures_excluded.py` and any future catalogue seed for clause 3.

**Why existing rules do not cover it:** P-8 forbids *building* speculative capability, not
*fabricating a result* from one that was not built. P-30 requires a caught error to be handled — it
says nothing where no error occurs. P-14 asks for unsurprising behaviour without prohibiting a
synthesized success. `90-functional-knowledge.md` classifies *documentation* of inert surfaces
("Wired but inert", "Test-only") and explicitly authorizes nothing about implementation. No rule
mentions fixtures other than as test fixtures.

**The decision required of a human:** either (a) accept an ADR migrating these two clauses into a
`.claude/rules/**` file, or (b) record explicitly that they lapse with the scaffold phase and accept
that `test_fixtures_excluded.py` then enforces an unstated requirement. **Option (b) is a decision,
not a default.** Until one is taken, the fifteen `Principle IX` citations are left in place, because
removing them would silently drop the only remaining in-tree pointer to the requirement.

## 7. Generated artifacts

`build/contracts/**` is generated by `ragcore/scripts/emit_contracts.py` and
`integrations/scripts/emit_contracts.py` from Pydantic model docstrings, and
`.github/workflows/contracts.yml` fails when the committed tree is stale.

- **Nothing under `build/contracts/**` was hand-edited.** The directory was excluded from the
  mechanical pass by path.
- Three citations lived in generated `description` strings. Their **sources** were repointed
  (`ragcore/src/ragcore/api/customer/routes.py`, `application/ports.py`, `domain/work.py`,
  `domain/governance.py`) and the artifacts regenerated with the repository's own emitters.
- `ragcore/tests/contracts/test_openapi_contracts.py::test_the_committed_document_matches_the_generated_one`
  failed before regeneration and passes after — the staleness gate did its job.
- One regeneration exposed a defect introduced by the mechanical pass: a source docstring already
  cited `ADR-0004` alongside `Principle VIII`, producing `(ADR-0004, ADR-0004)`. Fixed at source in
  `ExecutionTreatment.cs` and `domain/governance.py`, then re-emitted.
- `build/contracts/dotnet/**` is emitted from .NET XML docs; none of its text carried a citation, and
  its committed content is unchanged.

## 8. Authority consistency

No current instruction names `.specify/memory/constitution.md`, `.specify/**`, `specs/**`, or a Spec
Kit plan, task list or contract as **current authority**.

| Surface | Result |
|---|---|
| `CLAUDE.md` | §10 names them history; §2 names the constitution non-authoritative migration input. **Updated** — its claim that the stale pointers were confined to `apps/**` and `.github/workflows/**` was the B13-2 scope error and is corrected |
| `.claude/rules/00-authority.md` | §00.2 and §00.4 exclude them by path |
| `.claude/rules/70-adr.md`, `90-functional-knowledge.md` | exclude them by path |
| `.claude/rules/22`, `23`, `24`, `40-testing.md` | cite them **only** as migration input, each saying so in the same paragraph |
| `.claude/skills/**` | four procedural skills; `adr-author` lists `.specify/**` among non-authority |
| `.claude/settings.json` | three PreToolUse hooks; **no** `speckit` or `.specify` reference |
| `README.md` | names them history, not authority |
| Serena memories | `core.md` names them not-authority. `task_completion.md` **was stale** — it claimed the per-change matrix was "not fully mirrored" and D-11-2 open. **Corrected** to point at §40.8/§40.9 and record D-11-2 closed |
| Governance guards | `test_guards.py` asserts non-authority and asserts the absence of Spec Kit mechanism |
| CI / build | `.gitignore` carried two stale citations (§Commits and versioning, §Secrets); **repointed**. No workflow reads Spec Kit |

## 9. Context loading — Phase 12 strategy intact

| Layer | State |
|---|---|
| Global (no `paths:`) | `00`, `10`, `30`, `40`, `50`, `60`, `70`, `80`, `90` — nine, unchanged |
| `dotnet/**` | `20-dotnet.md` |
| `ragcore/**`, `integrations/**` | `21-python.md` |
| `apps/**` | `22-web-typescript.md` |
| `apps/web/**` | `23-angular.md` |
| `apps/desktop/**` | `24-electron.md` |
| Skills | `adr-author`, `db-change`, `functional-update`, `langgraph-change` — procedural only |

`CLAUDE.md` declares **no `@` imports**, so no rule is forced into every session. No rule file was
added, removed or duplicated. No rule text was copied to avoid a cross-reference.

## 10. Governance self-containment

Every normative area is defined inside `.claude/**` without reference to Spec Kit for its content:

| Area | Where | Depends on Spec Kit? |
|---|---|---|
| Authority model | `00-authority.md` | no — names Spec Kit only to exclude it |
| Engineering baseline | `10-principles.md`, `20-dotnet.md`, `21-python.md` | no |
| Frontend baseline | `22`, `23`, `24` | no — constitution named as migration input only |
| Testing baseline | `40-testing.md` incl. §40.8–§40.10 | no — same |
| ADR process | `70-adr.md` + `adr-author` + `adr_structure_guard.py` | no |
| DB gate | `50-database.md` + `db-change` + `db_migration_guard.py` | no |
| LangGraph gate | `30-langgraph.md` + `langgraph-change` + `langgraph_change_guard.py` | no |
| Functional knowledge | `90-functional-knowledge.md` + `functional-update` | no |
| Security / operations | `80-security-ops.md` | no |
| Cross-gate ordering | `60-architecture-gates.md` | no |

**Deleting `.specify/**` and `specs/**` removes no normative content that current governance still
requires — with the single exception of Principle IX clauses 2b and 3 (§6), which is why that is a
blocker rather than a note.** The trees were not deleted to establish this.

## 11. Phase 16 deletion manifest

Verified against the tree, not inherited from Phase 13. Historical references in
`docs/migration/**` and `docs/adr/**` are deliberately **not** listed: they stay.

| # | File | Reference | Why deletion invalidates it | Kind | Phase 16 action |
|---|---|---|---|---|---|
| **M-01** | `.dockerignore:86` | `specs/` | pattern matches nothing | current | delete the line |
| **M-02** | `CLAUDE.md` §10 | "remain in the tree pending a later retirement phase" | no longer true | current | rewrite as completed history |
| **M-03** | `README.md:40–41` | "retained pending a later retirement phase" | no longer true | current | rewrite as completed history |
| **M-04** | `.claude/rules/00-authority.md` §00.4 | "remain in the tree pending a later retirement phase" | no longer true | current | rewrite as completed history; **keep** the non-authority statement |
| **M-05** | `.claude/rules/70-adr.md:19` | `.specify/**`, `specs/**` in the non-authority list | paths gone | current | keep or move to past tense; harmless either way |
| **M-06** | `.claude/rules/90-functional-knowledge.md:53` | same, in the non-evidence list | paths gone | current | as M-05 |
| **M-07** | `.claude/skills/adr-author/SKILL.md:100` | same | paths gone | current | as M-05 |
| **M-08** | `.claude/rules/22-web-typescript.md:53,59` | `.specify/memory/constitution.md` as migration input | file gone | historical provenance | **keep**; note the source was deleted in Phase 16 |
| **M-09** | `.claude/rules/40-testing.md:171` | same | file gone | historical provenance | as M-08 |
| **M-10** | `.claude/rules/23-angular.md:102` | `specs/001-platform-scaffold/plan.md` §Dependency direction as the rule's only prose source | source gone | historical provenance (**FE-AMB-3**) | **keep** — the rule text is stated in full in the file; only the provenance becomes historical |
| **M-11** | `.serena/memories/core.md:16,38` | both trees described as retained | no longer true | memory | update to "deleted in Phase 16" |
| **M-12** | `.claude/hooks/test_guards.py:842–906` | `speckit`/`.specify` regexes | — | **active guard** | **keep unchanged** — they assert *absence*, and remain correct and necessary after deletion |
| **M-13** | `apps/desktop/src/main/endpoint-execution-boundary.ts:59` | runtime error text cites `specs/001-platform-scaffold/plan.md` Stage 4 | user-visible message points at a deleted file | **runtime string** | repoint to ADR-0004 / ADR-0006; check the Electron suite for an assertion on the text |
| **M-14** | `ragcore/workers/expiry_sweep.py:105`, `ingestion_run.py:123`, `integration_result_worker.py:205`, `outbox_dispatch.py:201`, `resume_worker.py:147`, `retention_sweep.py:247`; `integrations/workers/command_consumer.py:103` | `NotImplementedError` messages cite `specs/.../tasks.md` | same | **runtime strings** | repoint or drop the pointer; keep the message's substance |
| **M-15** | `ragcore/src/ragcore/api/customer/sample_flows.py:119` **and** `build/contracts/ragcore/customer.v1.openapi.json:435` | docstring cites `T241` in `specs/.../tasks.md`; the contract is generated from it | generated text points at a deleted file | source + **generated** | fix the docstring, then **regenerate** with `scripts/emit_contracts.py`; never hand-edit the JSON |
| **M-16** | `build/infra/apim/apis.json:8`, `build/infra/messaging/queues.json:5` | prose pointers to `specs/.../contracts/` | sources gone | config comments | repoint to `build/contracts/**` or drop |
| **M-17** | `docs/current-implementation/file-map.md:260` | describes the `specs/` tree as present | no longer true | non-authoritative doc | update or mark historical |
| **M-18** | `docs/architecture/integrations-service-delta.md:9–11,140,162` | source-material list and a Principle V reconciliation row | sources gone | non-authoritative doc | **keep** — it is a dated reconciliation record |

**M-13, M-14 and M-15 are the only items that touch shipped artifacts**, and all three are message
or docstring text with no behavioural effect. **No speculative change was made to any of them in
Phase 15.**

## 12. Validation

All commands run from the Phase 15 worktree.

| Gate | Command | Result |
|---|---|---|
| Governance guards | `python .claude/hooks/test_guards.py` | **792/792 checks passed** |
| RagCore lint | `uv run ruff check .` | **All checks passed** |
| RagCore format | `uv run ruff format --check .` | **248 files already formatted** |
| RagCore types | `uv run mypy` | **no issues in 219 source files** |
| RagCore tests | `uv run pytest -q` | **1301 passed** |
| Integrations lint | `uv run ruff check .` | **All checks passed** |
| Integrations format | `uv run ruff format --check .` | **68 files already formatted** |
| Integrations types | `uv run mypy` | **no issues in 67 source files** |
| Integrations tests | `uv run pytest -q` | **155 passed** |
| .NET build | `dotnet build` | **succeeded — 0 Warning(s), 0 Error(s)** (`TreatWarningsAsErrors` on) |
| .NET tests | `dotnet test` | **all passed** — ArchitectureTests 88, ContractTests 51, module suites green |
| .NET format | `dotnet format --verify-no-changes` | **fails — DV-14**, 7246 errors, **every one `ENDOFLINE`** |
| Boundaries | `bash build/scripts/check-boundaries.sh` | **4/4 checks passed** |
| Edge path | `bash build/scripts/check-edge-path.sh` | **Edge path intact** |
| Desktop types | `npm run typecheck` | **exit 0** |
| Desktop lint | `npm run lint` | **exit 0** |
| Desktop tests | `npx vitest run` | **178 passed, 4 files** |
| Web lint | `npx eslint .` | **exit 0** |
| Web format | `npx prettier --check .` | **All matched files use Prettier code style** |
| Web types | `npx tsc -b` (after `npm run build:libs`) | **exit 0, no errors** — see DV-13 below |
| Web tests | `npm test` | **passed** — unit suites green, architecture suite 9/9 |

Contract staleness was caught and cleared: `test_the_committed_document_matches_the_generated_one`
failed on the first run (1 failed / 1300 passed), and passes after regeneration (1301 passed).

### 12.1 Known deviations

| Deviation | State after Phase 15 |
|---|---|
| **DV-14** — `dotnet format --verify-no-changes` fails locally on Windows CRLF | **OPEN, and verified still failing.** Every one of the 7246 errors is `ENDOFLINE`; there is no formatting or style error of any other kind. CI runs on Linux. **Not repaired** (`00-authority.md` §00.7) |
| **DV-13** — `apps/web` `npx tsc -b` fails on 2 pre-existing `readHostedConfig` errors | **OPEN, and NOT REPRODUCED here.** In this worktree `npx tsc -b` exits 0 after `npm run build:libs`. `apps/**` is byte-identical to Phase 14 (`git status --porcelain apps` is empty), so **nothing in Phase 15 could have fixed it** and the difference is a build-state artifact of a fresh checkout. **DV-13 is NOT claimed resolved**; it needs a deliberate re-verification against the Phase 13/14 conditions |
| **EG-10** — no mechanism binds a diff to the categories §40.9 says it owes | **OPEN**, unchanged. Building one is a separate human decision |

## 13. Negative validation — nothing was weakened

| Protection | State |
|---|---|
| No `speckit-*` skill | **confirmed** — guard asserts it; four procedural skills remain |
| No active `.specify` execution | **confirmed** — no hook, setting, workflow, script or test reads the tree |
| No current authority points to Spec Kit | **confirmed** (§8) |
| ADR-0010 Accepted | **unchanged** |
| ADR-0011 Accepted | **unchanged** |
| Fifteen testing categories present | **confirmed** — TC-01…TC-15 |
| CM-01…CM-12 present | **confirmed** |
| Coverage non-gating | **confirmed** — no coverage threshold in any workflow |
| Frontend baseline path-scoped | **confirmed** — `apps/**`, `apps/web/**`, `apps/desktop/**` |
| DB / LangGraph / ADR gates operational | **confirmed** — three PreToolUse hooks registered and green |
| No test weakened | **confirmed** — no test deleted, skipped, `xfail`ed, loosened or narrowed. Test counts rose or held: RagCore 1301, Integrations 155, Desktop 178, .NET ArchitectureTests 88 / ContractTests 51, web architecture 9 |
| `.specify/**`, `specs/**` untouched | **confirmed** — `git status --porcelain .specify specs` empty |
| No application, database, LangGraph or architecture behaviour changed | **confirmed** — changes are comments, docstrings, config comments, build-manifest comments, governance records, and two regenerated contract `description` strings whose text is documentation |

## 14. Remaining blockers

| Id | Blocker |
|---|---|
| **B15-1** | **Principle IX clauses 2b and 3 are unique normative content with no surviving home.** Deleting `.specify/**` and `specs/**` destroys the only written statement of a requirement the repository mechanically enforces (`ragcore/tests/governance/test_fixtures_excluded.py`). A human decision under the ADR gate is required first — §6.1 states the exact text, scope and options. Claude wrote no rule and no ADR |

Not blockers, recorded and open: the eight ambiguous cross-stack citations (§4.4), DV-13, DV-14,
EG-10, and the M-13/M-14/M-15 runtime-string repointing, which is Phase 16's own work.

## 15. Deletion-readiness verdict

Phase 15 met every objective except one, and the exception is a governance stop rather than an
incomplete task: B13-2 is closed, the Phase 13 count is corrected, the Phase 14 migration is
independently validated, no active Spec Kit dependency exists, no current authority points at Spec
Kit, the deletion manifest is exact and evidence-based, and `.specify/**` and `specs/**` are
untouched. B13-3 resolved into two genuinely unique normative clauses, and the brief requires those
to stop for a human rather than be silently dropped.

```text
NOT READY FOR PHASE 16 — B15-1: constitution Principle IX clauses 2b (no silent degradation,
stubbed success or fabricated result) and 3 (reference fixtures are labelled, inert, excluded
from production configuration and never a use case) are unique normative requirements with no
home in .claude/rules/**. They are mechanically enforced by
ragcore/tests/governance/test_fixtures_excluded.py and stated only in .specify/memory/constitution.md
and specs/001-platform-scaffold/spec.md, both inside the deletion set. A human must either accept
an ADR migrating them into the engineering baseline, or explicitly record that they lapse.
Deleting the trees before that decision destroys a requirement the repository still enforces.
```

Everything else in the deletion path is ready. Once B15-1 is decided, Phase 16 is the manifest in
§11 and nothing more.
