# Phase 11 — Spec Kit retirement readiness and dependency audit

| | |
|---|---|
| **Phase** | 11 — retirement readiness audit (audit and classification only) |
| **Date** | 2026-09-21 |
| **Branch** | `speckit-to-claude` |
| **Revision audited** | `d15b59f6fef747de05ff3f30b67a6d93081f4571` |
| **Working tree** | clean at audit start |
| **Tracked files** | 845 (`git ls-files`) |
| **Predecessor** | `docs/migration/phase-10-baseline-reconciliation.md` (commit `d15b59f`, present and is `HEAD`) |
| **Scope** | Audit, dependency classification, replacement verification, prerequisite matrix, proposed delta |
| **Not in scope** | Retiring, deleting or editing any Spec Kit artifact; resolving any open decision; changing architecture, application code, configuration or tests |

---

## 1. Executive result

```text
PHASE 11 NOT READY FOR RETIREMENT
```

**Two blockers.** Neither is an engineering deviation, and neither is a missing Claude
replacement.

| # | Blocker | Classification |
|---|---|---|
| **B11-1** | `README.md` and `.serena/memories/**` still declare `.specify/memory/constitution.md` and `specs/001-platform-scaffold/**` to be **current authority** for engineering governance and technical realization; and the ten `speckit-*` skills are **live, invocable Claude skills** that execute `.specify/scripts/**` and load the constitution as governance | **active Spec Kit dependency** |
| **B11-2** | **B-4 / UD-1** — the retired constitution is the only text in the repository that states Angular and Electron engineering rules (Principle VII, §Angular, §Electron), and roughly thirty-five live source and CI surfaces cite it by name as the rationale for their assertions. Retirement removes that text. Which of the three documented options applies is not Claude's to choose | **human decision required** |

**What is *not* a blocker.** The migrated `.claude/rules/` baseline, the four gates, the
architecture authorities, the functional record and ADR governance are all self-contained and
carry **no** active Spec Kit dependency. Every reference to Spec Kit inside
`CLAUDE.md`, `.claude/rules/**` and the four active governance skills is **exclusionary** — it
names Spec Kit in order to deny it authority. That is the correct shape and is evidence of
readiness, not against it.

**No Spec Kit path is read at runtime anywhere outside the Spec Kit trees.** A targeted search for
file-opening, path-resolution and import constructs against `.specify` or `specs/` across all 845
tracked files returned **zero** matches. Every remaining reference is prose in a comment,
docstring, error message or Markdown table.

---

## 2. Revision audited

```text
branch          speckit-to-claude
commit          d15b59f6fef747de05ff3f30b67a6d93081f4571
subject         docs(governance): reconcile BL-10 migration ownership with Alembic (phase 10)
ancestry        d15b59f is HEAD; Phase 10 is present, not merely reachable
working tree    clean (git status --porcelain empty)
tracked files   845
```

Repository content throughout this document is established with `git ls-files` and `git grep`.
Untracked and generated residue (`bin/`, `obj/`, `.venv/`, `__pycache__/`, `node_modules/`,
Angular cache, packaging output) is excluded, per `.claude/rules/00-authority.md` §00.4.

---

## 3. Current Claude governance inventory

All 31 tracked paths under `.claude/`, plus the root instruction file.

### 3.1 Root instruction

| Path | Role |
|---|---|
| `CLAUDE.md` | The map. Names the three architecture authorities, the baseline sources, the authority hierarchy, the rule index, the four gates, and §10 "Retired Spec Kit artifacts are not authoritative" |

### 3.2 Rules — 12 files, the operative engineering and governance baseline

| Path | Scope |
|---|---|
| `.claude/rules/00-authority.md` | repository-wide — authority, precedence, conflicts, deviations, non-inference |
| `.claude/rules/10-principles.md` | repository-wide — P-1…P-32, C-1…C-6 |
| `.claude/rules/20-dotnet.md` | `dotnet/**` |
| `.claude/rules/21-python.md` | `ragcore/**`, `integrations/**` |
| `.claude/rules/22-web-typescript.md` | `apps/web/**`, `apps/desktop/**` — status: baseline **not defined**, deliberately |
| `.claude/rules/30-langgraph.md` | LangGraph change control |
| `.claude/rules/40-testing.md` | repository-wide testing policy |
| `.claude/rules/50-database.md` | database engineering and change control |
| `.claude/rules/60-architecture-gates.md` | cross-gate ordering, conformance findings |
| `.claude/rules/70-adr.md` | ADR requirements and change governance |
| `.claude/rules/80-security-ops.md` | repository-wide security and operational policy |
| `.claude/rules/90-functional-knowledge.md` | the implemented-truth record |

### 3.3 Skills — 14 tracked, of which 4 are active Claude governance procedures

| Path | Status |
|---|---|
| `.claude/skills/adr-author/SKILL.md` | **active** — ADR gate procedure |
| `.claude/skills/db-change/SKILL.md` | **active** — DB gate procedure |
| `.claude/skills/langgraph-change/SKILL.md` | **active** — LangGraph gate procedure |
| `.claude/skills/functional-update/SKILL.md` | **active** — functional record procedure |
| `.claude/skills/speckit-analyze/SKILL.md` | **Spec Kit mechanism** — see §4.3 |
| `.claude/skills/speckit-checklist/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-clarify/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-constitution/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-converge/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-implement/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-plan/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-specify/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-tasks/SKILL.md` | Spec Kit mechanism |
| `.claude/skills/speckit-taskstoissues/SKILL.md` | Spec Kit mechanism |

### 3.4 Hooks and settings

| Path | Role | Spec Kit coupling |
|---|---|---|
| `.claude/hooks/_guardlib.py` | shared guard library, worktree-aware path normalization | none |
| `.claude/hooks/db_migration_guard.py` | H2 | none |
| `.claude/hooks/langgraph_change_guard.py` | H3 | none |
| `.claude/hooks/adr_structure_guard.py` | H5 | none |
| `.claude/hooks/test_guards.py` | the governance suite — 486 checks | **two assertions** (§5.3) |
| `.claude/settings.json` | wires H2, H3, H5 on `PreToolUse` | none — no Spec Kit command is invoked |
| `.claude/settings.local.json` | developer-local; the suite asserts it carries no `hooks` override | none |

### 3.5 Suite result at the audited revision

```text
$ python .claude/hooks/test_guards.py
486/486 checks passed
```

Nothing was deleted, skipped, loosened or narrowed to obtain that result. No test, configuration,
architecture document, application file or Spec Kit artifact was modified in this phase.

---

## 4. Spec Kit artifact inventory

66 tracked paths in three groups.

### 4.1 `.specify/**` — 21 files, the Spec Kit mechanism itself

| Group | Paths |
|---|---|
| State / config | `.specify/.gitignore`, `.specify/init-options.json`, `.specify/integration.json` |
| Integration manifests | `.specify/integrations/claude.manifest.json`, `.specify/integrations/speckit.manifest.json` |
| Governance source | `.specify/memory/constitution.md` (968 lines), `.specify/memory/.constitution-template.json` |
| Executable scripts | `.specify/scripts/powershell/{check-prerequisites,common,create-new-feature,resolve-template,setup-plan,setup-tasks}.ps1` |
| Templates | `.specify/templates/{checklist,constitution,plan,spec,tasks}-template.md` |
| Workflow | `.specify/workflows/speckit/workflow.yml`, `.specify/workflows/workflow-registry.json` |

`.specify/integrations/claude.manifest.json` records, with SHA-256 digests, that the ten
`.claude/skills/speckit-*/SKILL.md` files were **installed into the Claude surface by Spec Kit**
at `2026-09-15T12:20:30Z`, integration version `1.0.5`. `.specify/integration.json` names
`claude` as the default and only installed integration. The two trees are one mechanism, not two.

### 4.2 `specs/**` — 24 files, one feature directory

`specs/001-platform-scaffold/` holds `spec.md`, `plan.md`, `tasks.md`, `data-model.md`,
`research.md`, `quickstart.md`, `contract-freeze.md`, `implementation-freeze.md`, four
`stage-N-notes.md`, three `checklists/*.md` and nine `contracts/*.md`.

### 4.3 The ten `speckit-*` skills — Spec Kit mechanism living inside `.claude/`

These are not inert Markdown. They are **registered, invocable Claude skills at this revision**,
and their instructions execute the Spec Kit mechanism. Verified in
`.claude/skills/speckit-plan/SKILL.md`:

```text
line  5  compatibility: "Requires spec-kit project structure with .specify/ directory"
line 25  Check if `.specify/extensions.yml` exists in the project root.
line 60  Run `.specify/scripts/powershell/setup-plan.ps1 -Json` from repo root ...
line 62  Read FEATURE_SPEC and `.specify/memory/constitution.md`.
line 66  Fill Constitution Check section from constitution
```

This is the most consequential finding of the audit, and it cuts **for** retirement rather than
against it: at the audited revision the repository offers **two** engineering-governance sources
to an agent — the migrated `.claude/rules/` baseline, and `.specify/memory/constitution.md`
reachable through a live skill. `.claude/rules/00-authority.md` §00.1 admits exactly one.

---

## 5. Spec Kit dependency audit

### 5.1 Method

`git grep` over all tracked files for `.specify`, `specs/`, `speckit`, `Spec Kit`, `constitution`,
`spec.md`, `plan.md`, `tasks.md`, `research.md`, `quickstart.md`, and separately for
path-consuming constructs (`open(`, `Path(`, `read_text`, `resolve`, `join`, `import`, `require`,
`source`, `cat`) applied to a `.specify` or `specs/` literal.

### 5.2 The decisive negative result

```text
Runtime reads of .specify/** or specs/** outside the Spec Kit trees:   0
Spec Kit invocations in .github/workflows/**, build/** or dev.sh:      0
Spec Kit commands in .claude/settings.json:                            0
```

**No build, test, CI job, hook or application code path opens a Spec Kit file.** Deleting
`.specify/**` and `specs/**` would break no executable behaviour. Everything that remains is
prose, and prose is classified below.

### 5.3 Active dependencies — class A

| # | File | Exact reference | What depends on it | Claude equivalent | Required retirement action |
|---|---|---|---|---|---|
| **A-1** | `.claude/skills/speckit-*/SKILL.md` (x10) | `.specify/scripts/powershell/*.ps1`, `.specify/memory/constitution.md`, `.specify/extensions.yml` | The skills are registered and invocable; invoking one runs the Spec Kit mechanism and loads the constitution as governance | `.claude/rules/**` for governance; `.claude/skills/{adr-author,db-change,langgraph-change,functional-update}` for procedure. **The *feature-authoring* function has no Claude equivalent and, per §12, needs none** | **Remove all ten.** They are the retired mechanism installed into the Claude surface |
| **A-2** | `.claude/hooks/test_guards.py:842-843` | `speckit = sorted((ROOT / ".claude/skills").glob("speckit-*/SKILL.md"))` then `check("Spec Kit skills still present", len(speckit) == 10)` | The governance suite **fails** if the ten skills are removed | n/a — the assertion exists to protect Spec Kit during migration | **Update in the same change as A-1.** This is a deliberate governed inversion of an assertion whose subject is being retired, not the weakening of a test (`.claude/rules/40-testing.md` §40.1). The replacement asserts the opposite invariant: no `speckit-*` skill is present |
| **A-3** | `.claude/hooks/test_guards.py:1107` | `check("CLAUDE.md says Spec Kit artifacts are not authoritative", "not authoritative" in claude_text.lower())` | `"not authoritative"` occurs **exactly once** in `CLAUDE.md`, at the §10 heading. Rewriting §10 breaks this check | n/a | **Update in the same change as the `CLAUDE.md` §10 rewrite** |

A-2 and A-3 are the only two places in the entire governance machinery that depend on Spec Kit
being present. Both are in one file, both are narrow, and both are *protective* assertions written
to stop Spec Kit being removed accidentally. They did their job.

### 5.4 Stale references — class C

These tell a current developer, or a current assistant, to use Spec Kit as authority. Each
contradicts `.claude/rules/00-authority.md` §00.4.

| # | File | Exact reference | Why stale | Claude equivalent | Required retirement action |
|---|---|---|---|---|---|
| **C-1** | `README.md:16-20` | An "Authoritative documents" table naming `Synthia-Platform-Specification.md` (**Architecture**), `.specify/memory/constitution.md` (**Engineering governance — how software is built, tested, reviewed, secured**), `specs/001-platform-scaffold/plan.md` (**Technical realization**), `specs/001-platform-scaffold/tasks.md` (**Executable work**) | Three of the four are named **non-authoritative** by `00-authority.md` §00.4 by exact path. The README is the repository's front door and currently routes every new developer to the retired mechanism | `CLAUDE.md`; A1/A2/A3; `.claude/rules/**`; `docs/functional/implemented.md` | **Update.** Replace the table with the current authority model. `README.md` never mentions `CLAUDE.md` or `.claude/rules/` at all |
| **C-2** | `README.md:72` | `specs/  Specification, plan, tasks, contracts, checklists` in the Layout block | Describes a tree being retired | — | Update or drop the line |
| **C-3** | `README.md:235` | Links `specs/001-platform-scaffold/tasks.md` §Deferred as the record of intentional omissions | `docs/functional/implemented.md` is the implemented-truth record (`90-functional-knowledge.md`) | `docs/functional/implemented.md` | Update |
| **C-4** | `README.md:146, 224` | `(constitution Principle I)`, `(constitution §Non-functional commitments)` | Cites retired governance as the reason for a current instruction | `.claude/rules/**` | Update the citation |
| **C-5** | `.serena/memories/core.md:7-8, 29-30` | *"`.specify/memory/constitution.md` — engineering governance (principles I–X, baselines, gates)"*; *"`specs/001-platform-scaffold/{plan,tasks}.md` — technical realization / executable work"*; *"`.specify/` — spec-kit (speckit-* skills) templates & scripts"* | A **live assistant-instruction surface**. `00-authority.md` §00.4 names `.serena/**` non-authoritative, but a memory is loaded and acted on, so a stale one misdirects work | `CLAUDE.md`, `.claude/rules/**` | **Update.** Same change as C-1 |
| **C-6** | `.serena/memories/task_completion.md:3, 14, 16` | *"Merge requires ALL gates pass ... (constitution §Quality gate)"*; *"update OpenAPI under `specs/001-platform-scaffold/contracts/`"*; *"Required test categories ... constitution §Which change requires which category"* | Directs contract changes into the retiring tree and cites the retired constitution for the test-category matrix | `.claude/rules/40-testing.md`; `.github/workflows/contracts.yml` | **Update.** Note: the test-category matrix has no `.claude/rules/` equivalent — see **D-11-2** |
| **C-7** | `.serena/memories/conventions.md:3`, `.serena/memories/web/core.md:1` | `## Cross-cutting (constitution)`; `never security boundaries (constitution VII)` | Retired citation | `10-principles.md` P-17; the Electron security suite | Update the citation |
| **C-8** | `docs/adr/README.md:31` | **OQ-01** row citing `Specification §40; spec.md §Dependencies` | An open-question index entry pointing into the retiring tree | — | **Review manually** — the pointer is historical context for an open question, not an instruction |

### 5.5 Historical references — class B

Left as they are. Each is explicitly about the past, or is an exclusion.

| Group | Files | Nature |
|---|---|---|
| **Exclusionary governance references** | `CLAUDE.md` §10; `00-authority.md` §00.4; `70-adr.md` §70.1; `90-functional-knowledge.md` §90.2; `adr-author/SKILL.md` | Every one names Spec Kit **in order to deny it authority**. Removing the artifacts does not remove the need for the statement; §15.2 addresses the wording |
| **Migration records** | `phase-2-authority-model.md`, `phase-2-coverage-matrix.md`, `phase-7-validation.md`, `phase-8-worktree-guard.md`, `phase-9-baseline-input.md`, `phase-9-baseline-coverage.md`, `phase-10-baseline-reconciliation.md`, and this document | The migration record. **Preserve unchanged** |
| **Accepted ADRs 0001–0009** | `0006`, `0008`, `0009` cite `specs/**` and `spec.md` | Historical records (`70-adr.md` §70.6: never renumbered, reworded or "corrected"). **Preserve unchanged** |
| **Implementation comments and messages** | `ragcore/workers/{expiry_sweep,ingestion_run,integration_result_worker,outbox_dispatch,resume_worker,retention_sweep}.py`; `integrations/workers/command_consumer.py`; `ragcore/src/ragcore/api/customer/sample_flows.py`; `ragcore/tests/contracts/test_api_surface.py`; `apps/desktop/src/main/endpoint-execution-boundary.ts`; `apps/web/projects/platform-core/src/lib/contracts/primitives.ts`; `dotnet/src/Synthia.Contracts/Querying/SortSpec.cs`; `build/infra/apim/apis.json`; `build/infra/messaging/queues.json`; `build/contracts/ragcore/customer.v1.openapi.json` | Prose citing `specs/001-platform-scaffold/{tasks,plan,contracts}` as the origin of a deferral or a contract. **None is read at runtime.** They become dangling citations after retirement, not broken code. **Review manually** — §15.4 M-6 |
| **`constitution` citations in CI and lint prose** | `.github/workflows/{desktop,edge,integrations,ragcore}.yml`; `.gitignore`; `build/scripts/{check-boundaries.sh,check-edge-path.sh,openapi_validate.py}`; `apps/desktop/**` (~20 files); `apps/web/**` (~15 files) | Comments and lint messages citing the retired constitution as the *reason* a gate exists. The gates are real and stay. **Review manually** — and see **B11-2**, since the Electron/Angular citations are the ones whose source text disappears |
| **Non-authoritative architecture docs** | `docs/architecture/integrations-service-delta.md`, `docs/current-implementation/file-map.md` | Already named non-authoritative. Cite `specs/**` descriptively |
| **`.dockerignore:86`** | `specs/` | Excludes the tree from build context. Harmless before and after |

### 5.6 Ambiguous — class D

| # | Item | Why ambiguous |
|---|---|---|
| **D-11-1** | `specs/001-platform-scaffold/contracts/**` (9 files) | The generated OpenAPI under `build/contracts/**` is gated by `.github/workflows/contracts.yml`, and `20-dotnet.md` BL-6 makes the contract **code-first**. But `.serena/memories/task_completion.md:14` still directs contract edits into `specs/.../contracts/`, and `ragcore/tests/contracts/test_api_surface.py`'s docstring names `specs/001-platform-scaffold` as the frozen contract — **without reading it**. Whether those nine Markdown contracts hold anything the generated contracts do not is a content comparison this phase did not perform and must not guess at |
| **D-11-2** | The constitution's test-category matrix (*"which change requires which category"* — isolation, governance, approval, idempotency, concurrency, security markers) | `.claude/rules/40-testing.md` §40.5 names the test **kinds** the baseline requires, and the marker directories exist under `ragcore/tests/`. Whether §40.5 fully covers the constitution's per-change-type matrix is a content comparison, not an inventory question |
| **D-11-3** | `specs/001-platform-scaffold/tasks.md` §Deferred | Named by `README.md:235` and by seven worker modules as the register of deliberate omissions. `docs/functional/implemented.md` classifies behaviour as *Wired but inert* / *Not implemented*, which is the same information in the authoritative place — but whether it is the *same set* is a comparison, not an inventory |

---

## 6. Replacement coverage

A replacement is credited only where the Claude artifact **demonstrably carries the requirement**,
not because a similarly named file exists.

| Former Spec Kit responsibility | Former source | Current Claude replacement | Complete? | Retirement blocker? |
|---|---|---|---|---|
| **Engineering baseline** | `.specify/memory/constitution.md` §baselines | `.claude/rules/10,20,21,40,80` — 167 requirements, mechanically asserted at `test_guards.py:981` and `:1010`, traced in `phase-9-baseline-coverage.md` §3 | **Yes**, for .NET, Python, repository-wide | No |
| **Engineering baseline — TS/Angular/Electron** | constitution Principle VII, §Angular (line 715), §Electron (line 444) | `22-web-typescript.md` — principles-only, with §22.1 stating plainly that no stack baseline is defined and §22.4 recording the open decision | **No — deliberately not.** The gap is documented, not invented over | **Yes — B11-2** |
| **Architecture authority** | `Synthia-Platform-Specification.md` + `specs/.../spec.md` | A1 `identity-plane-final.md`, A2 `Synthia-OverallArchitecture-final.md`, A3 `RagAgent-Architecture-final.md`, fixed by `00-authority.md` §00.2 and asserted in `test_guards.py` | **Yes** | No |
| **Rules / principles** | constitution principles I–X | `10-principles.md` P-1…P-32 + C-1…C-6, each carrying `Source:` and an honest `Enforcement:` verdict | **Yes** | No |
| **Procedural workflows** | `speckit-plan`, `speckit-tasks`, `speckit-implement`, `speckit-analyze`, `speckit-converge`, `speckit-checklist`, `speckit-clarify` | `.claude/skills/{db-change,langgraph-change,adr-author,functional-update}` + the four gates in rules 50/30/70/90 | **Different, and sufficient.** Claude governs *changes by gate*, not *features by stage*. §12 verifies the resulting workflow end to end | No |
| **ADR governance** | `speckit-constitution`, constitution §ADR | `70-adr.md` + `adr-author` skill + H5 `adr_structure_guard.py`. Next number **0010** (§9) | **Yes** | No |
| **Testing governance** | constitution §Quality gate, §test categories | `40-testing.md` §40.1–§40.7, including the command table in §40.6 | **Yes** for policy, layout, the non-negotiable and the gate commands. The per-change-type matrix is **D-11-2** | No — ambiguity, not gap |
| **Functional knowledge** | `specs/.../spec.md`, `tasks.md §Deferred` | `docs/functional/implemented.md` + `90-functional-knowledge.md` + `functional-update` skill | **Yes** — §10 | No |
| **Architecture conformance** | constitution §conformance | `60-architecture-gates.md` §60.4 (report, never reconcile) and §60.5 (deviation vs finding) | **Yes** | No |
| **Development instructions** | `.specify/templates/**`, Spec Kit scripts | `CLAUDE.md` + `.claude/rules/**` | **Yes for Claude.** **No for a human reading `README.md`** — C-1 | **Yes — B11-1** |
| **Change gates** | constitution §gates | Four gates, one definition each, cross-gate ordering in `60-architecture-gates.md` §60.3, deterministic guards H2/H3/H5 wired in `.claude/settings.json` | **Yes** | No |
| **Feature specification / planning / task generation** | `speckit-specify`, `speckit-plan`, `speckit-tasks`, `speckit-taskstoissues` | **None, by design.** The retirement target does not require Claude to reproduce a feature-authoring pipeline; future feature requirements arrive with the feature | **n/a** | No |
| **Repository onboarding** | `README.md` → constitution + specs | `CLAUDE.md` for Claude. `README.md` still routes humans to Spec Kit | **No** | **Yes — B11-1 (C-1)** |

---

## 7. Engineering baseline readiness

Verified at the audited revision.

| Check | Result | Evidence |
|---|---|---|
| 167 requirements accounted for | **held** | `test_guards.py:981` `len(ALL_BASELINE_IDS) == 167`; `:1010` one matrix row per requirement; both green in the 486/486 run |
| `BL-10` reconciled to Alembic ownership | **held** | `phase-9-baseline-input.md` Appendix A.1 (amendment), `phase-10-baseline-reconciliation.md` §2–§3, `20-dotnet.md` BL-10, `50-database.md` §50.7. CF-1 / UD-3 **closed** |
| All rule files present | **held** | 12 files, §3.2; `test_guards.py` asserts `CLAUDE.md` indexes every one |
| Traceability intact | **held** | Every rule carries `Source:`; mapping in `phase-9-baseline-coverage.md` §6 |
| Language applicability explicit | **held** | Every rule file opens with a Scope table naming the paths it governs and the paths it does not |
| TypeScript baseline still undefined, not invented | **held** | `22-web-typescript.md` §22.1–§22.4. §22.3 preserves the existing gates while refusing to promote them to baseline |
| Deviations visible | **held** | DV-1…DV-11 in `phase-9-baseline-coverage.md` §8; EG-1…EG-8 in §5.4; each also stated inline in the owning rule |
| No source requirement silently dropped | **held** | §7 of the coverage record documents the dropped-rule recovery (C-1…C-5, DN-21 via defect D-3) |

**None of UD-1, UD-2, UD-4, UD-5, UD-6, UD-7 was resolved in this phase.** No explicit human
decision for any of them is present in the repository at `d15b59f`. Their individual retirement
impact is classified in §13.

---

## 8. TypeScript / Angular / Electron readiness

No TypeScript baseline is invented here, and none of the three documented options is chosen.

### 8.1 Did the repository rely on Spec Kit for TS-specific governance?

This is the question the phase brief asks, and it has a **two-part** answer that must not be
collapsed.

**Formally: no.** `.claude/rules/00-authority.md` §00.4 already names the retired constitution
non-authoritative by path. `22-web-typescript.md` §22.1 re-verified in Phase 9 that no
authoritative source defines a TS/Angular/Electron baseline. Nothing in current governance defers
to Spec Kit for these stacks. On the authority model alone, retirement changes nothing.

**Substantively: yes — the text exists only there.** `.specify/memory/constitution.md` carries:

```text
line 191  VII.  No Client Is a Security Boundary   [+ Angular and Electron baselines]
line 435  No client — Angular portal, Electron desktop ... is a security boundary
line 438  Angular. Role gating in the UI is convenience only ... bypassSecurityTrust* avoided
line 444  Electron. nodeIntegration=false, contextIsolation=true, sandbox=true where compatible.
line 445  A narrow contextBridge surface only: raw ipcRenderer MUST NEVER be exposed
line 449  Electron stays on a currently supported release, and file:// is ...
line 558  Angular — Angular DI, inject() where appropriate, no global mutable state
line 715  Angular — standalone components, strict TypeScript, feature-oriented organization
line 722  Current Angular testing defaults ... a state-management framework MUST NOT ...
```

And roughly thirty-five files under `apps/desktop/**` and `apps/web/**`, plus
`.github/workflows/desktop.yml` and `.github/workflows/edge.yml`, cite `constitution Principle VII`
**by name** as the stated reason their assertions exist — for example
`apps/desktop/eslint.config.js:35`:
`'No remote or dynamic code execution in the host (constitution Principle VII).'`

So the live Electron and Angular gates (`22-web-typescript.md` §22.3: `test:csp`, `test:a11y`, the
Electron security suite and its meta-guard) survive retirement intact — they are code, and code is
not deleted here. What does not survive is the **prose statement of the rules those gates enforce**,
and every in-repo pointer to it.

### 8.2 Classification of B-4 / UD-1

```text
B-4 / UD-1   BLOCKS RETIREMENT   —   classification: human decision required
```

Not "missing Claude replacement": `22-web-typescript.md` is a complete and accurate statement of
the current position, and §22.1's shortness is the report, not a stub. Not "active Spec Kit
dependency": no rule defers to the constitution. It blocks because **retirement is the act that
makes the choice irreversible in the tree**, and the three options carry different consequences:

| Option (from `22-web-typescript.md` §22.4) | Consequence at retirement | Instrument |
|---|---|---|
| **1 — principles-only** | The constitution's Angular/Electron text is dropped as superseded by `10-principles.md`; the live gates remain as tooling choices below the baseline | Explicit human confirmation that the *de facto* state is intended |
| **2 — separately supplied TS baseline** | The constitution's Angular/Electron content would be an **input** to that baseline, and must be preserved or migrated **before** `.specify/**` is removed | ADR (`70-adr.md` §70.2 B) |
| **3 — deliberately ungoverned** | Recorded decision that these stacks carry no baseline beyond the principles | ADR (`70-adr.md` §70.2 B) |

Under option 2 the retirement **order** changes: migration first, deletion second. That is why
this is a prerequisite and not a follow-up. **The choice is not Claude's, and is not made here.**

---

## 9. ADR readiness

| Check | Result | Evidence |
|---|---|---|
| Historical ADRs preserved | **held** | `docs/adr/0001`…`0009` all tracked and unmodified at `d15b59f` |
| Next number available from 0010 | **held** | Sequence `0001`…`0009` complete, no gaps, no duplicates, no placeholder. `70-adr.md` §70.6 and `CLAUDE.md` §8 both state `0010`. H5 asserts sequence continuity |
| ADR governance independent of Spec Kit | **held** | `70-adr.md` and `adr-author/SKILL.md` reference `.specify/**` and `specs/**` **only** in their non-authority exclusion lists. H5 `adr_structure_guard.py` contains **no** Spec Kit reference and reads only `docs/adr/*.md` |
| Existing ADRs are history, not active policy | **held** | `70-adr.md` §70.1 states `0001`…`0009` are historical records whose contents are not a source for reconstructing current architecture or baseline. Re-verified: `phase-10-baseline-reconciliation.md` §7.1 explicitly declines to treat Accepted `docs/adr/0002` as authority for the .NET read-only property |
| A3 inline ADR authority question classified | **held** — §9.1 | |

`docs/adr/0006`, `0008` and `0009` cite `specs/**` and `spec.md`. They are **preserved unchanged**
(`70-adr.md` §70.6: never renumbered, reworded or "corrected"). `docs/adr/README.md:31` carries
the **OQ-01** row pointing at `spec.md §Dependencies` — that is an index entry, not an ADR body,
and is listed as **C-8 / manual review** rather than an automatic edit.

### 9.1 OQ-5 — A3 inline ADR-001…ADR-012

`docs/architecture/RagAgent-Architecture-final.md` carries 25 matches for the inline
`ADR-001`…`ADR-012` identifiers. `70-adr.md` §70.1 states they are part of an authoritative
document and therefore authoritative, that they occupy a **different numbering space** from
`docs/adr/NNNN`, and that the two must never be conflated — while recording that confirmation of
that reading is **OQ-5**, still open.

```text
OQ-5   DOES NOT BLOCK RETIREMENT   —   classification: post-retirement governance decision
```

**Reasoning.** OQ-5 is a question about the relationship between two documents that both remain in
the tree after retirement: A3 (architecture authority, untouched) and `docs/adr/` (preserved
history). **Spec Kit is on neither side of it.** `.specify/**` and `specs/**` contain nothing that
would answer it, and removing them neither answers it nor makes it harder to answer. It is not a
historical-documentation issue either, because it governs how a *future* ADR must be numbered and
cited — a live governance concern. It is therefore a governance decision orthogonal to retirement,
takeable before or after it at identical cost.

One retirement-adjacent consequence, recorded and not acted on: `70-adr.md` §70.1's statement of
the question cites `docs/migration/phase-2-authority-model.md`, which is preserved under §15.3, so
the pointer survives.

---

## 10. Functional-knowledge readiness

| Check | Result | Evidence |
|---|---|---|
| The document exists and is governed | **held** | `docs/functional/implemented.md`; `90-functional-knowledge.md`; `functional-update` skill; named in `CLAUDE.md` §9 and asserted present by `test_guards.py` |
| Its authority is implementation truth, not architecture and not Spec Kit product spec | **held** | `90-functional-knowledge.md` §90.1 (*"it records; it never authorizes"*), §90.2 evidence policy, which names `.specify/**`, `specs/**`, A1/A2/A3, `docs/adr/**`, `docs/migration/**`, `README.md`, `Synthia-Platform-Specification.md` and `.claude/**` as things that are **never** evidence a capability is implemented |
| Not Spec Kit-derived | **held** | `implemented.md:12` states in its own methodology note that no design-intent source — *"notes, the platform specification, Spec Kit material or the Claude governance rules"* — was used as evidence. The document was built from implementation artifacts |
| Classification vocabulary sufficient | **held** | §90.5: Implemented / Implemented but unbound / Wired but inert / Test-only / Not implemented / Unverified. A richer vocabulary than a task list's done/deferred |
| Revision metadata present | **held** | §90.9 requires it; `implemented.md:18` names branch `speckit-to-claude` and the three commits audited |

### 10.1 Does a developer need `specs/**` to understand implemented behaviour?

**No, for behaviour.** `implemented.md` is built from implementation evidence and classifies inert
and unbound surfaces explicitly — which is precisely the information a `tasks.md` §Deferred
register carries, held in the authoritative place and under a rule that requires it to be
corrected rather than appended to (§90.6, §90.8).

**Two things are not resolved by inventory alone**, and are recorded rather than reconstructed
(`90-functional-knowledge.md` §90.2 forbids inferring them):

| Item | What might exist only in Spec Kit | Recorded as |
|---|---|---|
| The deferral register | Whether `specs/001-platform-scaffold/tasks.md` §Deferred names an omission that `implemented.md` does not classify. Seven worker modules and `README.md:235` cite it as the register | **D-11-3** — content comparison required before deletion |
| The frozen contracts | Whether `specs/001-platform-scaffold/contracts/**` (9 files) states a contract obligation absent from the generated OpenAPI under `build/contracts/**` | **D-11-1** — content comparison required before deletion |

**This phase does not rewrite `implemented.md`, and does not infer or reconstruct anything.** Both
items are listed under **Must review manually** in §15.4, not under Must remove.

---

## 11. Architecture readiness

| Question | Answer | Evidence |
|---|---|---|
| Are A1, A2, A3 sufficient without `Synthia-Platform-Specification.md`? | **Yes.** `00-authority.md` §00.2 fixes exactly three architecture authorities and names the Platform Specification as **not** one of them. `test_guards.py` asserts `CLAUDE.md` names all three | §00.2, §00.4 |
| ...without `.specify/**` and `specs/**`? | **Yes.** Both are named non-authoritative by exact path in §00.4, §70.1, §90.2 and `adr-author/SKILL.md` | as cited |
| ...without `integrations-service-delta.md` and `ragcore-langgraph-flow.md`? | **Yes.** Both sit in `docs/architecture/` and carry **no** authority — stated in `CLAUDE.md` §1, `00-authority.md` §00.2, `30-langgraph.md`, `70-adr.md` §70.1, `90-functional-knowledge.md` §90.2, and asserted mechanically at `test_guards.py:514` | as cited |
| Is either accidentally an **active** dependency of current governance? | **No.** Every reference to either file in active governance is an exclusion — it names the file in order to deny it authority. `test_guards.py:514` asserts `70-adr.md` **names** them, i.e. it protects the denial, not the content | §5.5 |

Neither file is deleted, moved or edited in this phase. `docs/current-implementation/file-map.md`
(itself non-authoritative under §00.4) cites `specs/**` descriptively at lines 253 and 260 and is
listed under manual review.

---

## 12. Feature-development readiness

> Could a future developer start a new feature using only Claude governance plus the authoritative
> architecture and functional sources, without needing Spec Kit?

**For an agent operating under `CLAUDE.md`: yes.** Each step of the required workflow has a named
owner, and each is enforced or procedurally defined:

| Workflow step | Owner | Enforcement at `d15b59f` |
|---|---|---|
| Understand request | `CLAUDE.md` "Delivering work"; `00-authority.md` §00.6 (stop on conflict) | procedural |
| Identify affected architecture / rule scope | `CLAUDE.md` §3 authority hierarchy; every rule file's Scope table; `00-authority.md` §00.5 precedence | procedural, with per-file scope statements |
| Check DB gate | `50-database.md` + `db-change` skill | **H2** `db_migration_guard.py`, wired in `.claude/settings.json` |
| Check LangGraph gate | `30-langgraph.md` + `langgraph-change` skill | **H3** `langgraph_change_guard.py`, wired |
| Check ADR gate | `70-adr.md` + `adr-author` skill | **H5** `adr_structure_guard.py`, wired |
| Cross-gate ordering when more than one fires | `60-architecture-gates.md` §60.3 — exactly one ordering per pairing; DB ordering wins over LangGraph | procedural, single-definition |
| Implement | `10-principles.md`, `20-dotnet.md`, `21-python.md`, `22-web-typescript.md`, `80-security-ops.md` | mechanical / partial / procedural, honestly stated per rule |
| Test | `40-testing.md`, incl. §40.6 command table per stack and §40.1 non-negotiable | CI workflows per stack |
| Update functional knowledge | `90-functional-knowledge.md` + `functional-update` skill | procedural, deliberately no hook (§90 preamble) |
| Validate architecture and governance | `60-architecture-gates.md` §60.6 test surface; `.claude/hooks/test_guards.py` | 486 checks, green |

**No step in that chain requires a Spec Kit artifact.** The absence of a product specification for
future features is not a defect — those requirements arrive with the feature.

**For a human reading `README.md`: no.** The front door still names the constitution as
engineering governance and `plan.md` / `tasks.md` as technical realization and executable work,
and never mentions `CLAUDE.md` or `.claude/rules/`. This is **C-1**, and it is the substance of
blocker **B11-1**.

---

## 13. Open-item classification

Classified against the retirement target, not against general desirability.

| ID | Description | Type | Blocks Spec Kit retirement? | Why | Human decision required? |
|---|---|---|---|---|---|
| **UD-1 / B-4** | TS/Angular/Electron baseline: principles-only, separately supplied, or deliberately ungoverned | Governance-scope decision | **YES** | The constitution is the only in-repo text stating Angular/Electron rules (§8.1), and ~35 live files cite it by name. Option 2 requires migrating that content **before** deletion, which changes the retirement order. The option chosen determines the delta | **Yes** — confirmation (opt. 1) or ADR (opt. 2, 3) |
| **UD-2** | `CA2007` / `DN-8`: accept the relaxation by ADR, or restore `severity = error` | Baseline deviation (DV-1) | **No** | A .NET analyzer-severity question, entirely inside `20-dotnet.md` and `dotnet/.editorconfig`. Spec Kit neither creates nor resolves it; rule and deviation both survive retirement unchanged | Yes, but independently |
| **UD-4 / D-2** | Truncated `BL-08` offset/limit requirement | Editorial defect in the baseline **input** | **No** | The malformation is in `docs/migration/phase-9-baseline-input.md`, which is **preserved** under §15.3. Retiring Spec Kit neither worsens nor repairs it. Every legible clause is migrated | Yes, but independently |
| **UD-5 / DV-10** | Add `T20` to ruff `select`, making `PY-4` mechanical | Enforcement gap / config change | **No** | A Python lint configuration decision. `PY-4` is binding either way (`21-python.md`). Unrelated to Spec Kit | Yes, but independently |
| **UD-6 / CF-2** | `BL-38` SDK container publish vs `BL-39` chiseled base | Genuine conflict between two clauses of the baseline **block** | **No** | Both sides live in `phase-9-baseline-input.md`, which is preserved. The conflict is recorded, unchosen, and reachable after retirement exactly as before. Phase 10 cited it as a *further* reason retirement was closed; against the retirement target it is not a prerequisite | Yes, but independently |
| **UD-7** | Whether and in what order to close **EG-1…EG-8** | Enforcement gaps | **No** | Each gap is an absent analyzer, check or CI step. All eight are recorded honestly in the owning rules and in `phase-9-baseline-coverage.md` §5.4. A rule whose enforcement is `currently-unenforced` is still binding. Building a new gate is explicitly a separate human-directed act (`40-testing.md` §40.7) | Yes, but independently |
| **OQ-5** | Are A3's inline ADR-001…ADR-012 authoritative? | Governance decision | **No** | Both sides (A3, `docs/adr/`) survive retirement untouched; Spec Kit is on neither side and contains nothing that answers it — §9.1 | Yes — **post-retirement** governance decision |
| **D-1** | `P-DN-S4` `realizes:` points at `DN19` (the `goto` rule) instead of DN-28/DN-29 | Editorial defect in `dotnet.yaml` | **No** | Both rules are migrated independently and in full, so no requirement is lost either way. Recorded in `20-dotnet.md` §20.1 | Human editorial correction, independently |
| **D-2** | See UD-4 | Editorial defect | **No** | as UD-4 | as UD-4 |
| **D-3** | `DN21`'s unquoted `text:` scalar truncates at `#` to the word `"Every"` under a YAML parser | Editorial defect in `dotnet_lang.yaml` | **No** | Already mitigated: the full text was recovered from the raw source line and DN-21 is migrated complete. The defect affects a source file that is preserved | Human editorial correction, independently |
| **D-4** | Five `.NET / C#`-scoped items (`BL-11`, `BL-12`, `BL-13`, `BL-29`, `BL-33`) are evidenced only by RagCore artifacts | Editorial / scoping defect in the Phase 9 record | **No** | Affects which stack five baseline items bind — a baseline question under `70-adr.md` §70.2 B(6). Spec Kit is not a party. Recorded, not repaired | Yes, but independently |
| **F-1** | The .NET deployable is read-only while A2 §7 and the baseline block assign it write-path responsibilities | **Architecture conformance finding** (implementation deviation) | **No** | `60-architecture-gates.md` §60.4 requires it to be recorded and **not** reconciled. It concerns A2 vs implementation; Spec Kit is on neither side. Retiring Spec Kit changes nothing about it | Yes — whether A2 §7 is met by the read-only split, or one side changes (ADR under §70.2 A(5)/(7)) |

### 13.1 F-1 and D-4 — effect surface

| Item | Claude governance | Spec Kit retirement | Architecture conformance | Application implementation |
|---|---|---|---|---|
| **F-1** | **No effect.** No `.claude/rules/` rule asserts the read-only property; it rests on implementation evidence and on `docs/adr/0002`, which §70.1 makes history | **No effect** | **Affected** — a recorded conformance finding under §60.4, open | **Affected in principle**, if the human decision goes that way. **Not touched here** |
| **D-4** | **Affected** — `20-dotnet.md` §20.8's recorded evidence for `BL-29`/`BL-33` points at RagCore revisions, and `BL-11`/`BL-12`/`BL-13` describe write semantics a read-only deployable cannot exercise | **No effect** | Indirectly — it is the scoping shadow of F-1 | **No effect.** Re-scoping is a baseline change, not an editorial fix |

Neither is fixed, and neither architecture nor application code is changed.

---

## 14. Retirement prerequisite matrix

| # | Prerequisite | Evidence | Status | Blocking? | Required action |
|---|---|---|---|---|---|
| **Governance** | | | | | |
| G-1 | Root `CLAUDE.md` is the entry point and self-contained | `CLAUDE.md`; every Spec Kit mention is exclusionary (§5.5) | **MET** | No | §10 wording updated with the delta (§15.2) |
| G-2 | 12 rule files present, scoped, traceable | §3.2; `test_guards.py` asserts `CLAUDE.md` indexes every one | **MET** | No | — |
| G-3 | 4 active governance skills present | §3.3 | **MET** | No | — |
| G-4 | `.claude/settings.json` wires H2/H3/H5 exactly once, no Spec Kit command | §3.4; `test_guards.py:846-857` | **MET** | No | — |
| G-5 | Hooks free of Spec Kit coupling | H2/H3/H5 and `_guardlib.py`: zero matches | **MET** | No | — |
| G-6 | Worktree enforcement | Phase 8; `phase-8-worktree-guard.md`; worktree checks green in the 486 run | **MET** | No | — |
| G-7 | Baseline coverage 167/167 | `test_guards.py:981`, `:1010` | **MET** | No | — |
| G-8 | Traceability `Source:` on every rule | `phase-9-baseline-coverage.md` §6 | **MET** | No | — |
| G-9 | Governance suite green | 486/486 at `d15b59f` | **MET** | No | Re-run after the delta |
| G-10 | No governance artifact *requires* Spec Kit | §5.2, §5.5 | **MET** | No | — |
| G-11 | `test_guards.py` does not *assert Spec Kit presence* | `:842-843` asserts exactly that; `:1107` depends on §10 wording | **NOT MET** | **Yes — sequencing** | Update both in the same change as the removal (A-2, A-3) |
| **Authority** | | | | | |
| A-1 | Architecture authority fixed at exactly A1/A2/A3 | `00-authority.md` §00.2; asserted in `test_guards.py` | **MET** | No | — |
| A-2 | Engineering baseline authority is `.claude/rules/**` | `00-authority.md` §00.3 | **MET** | No | — |
| A-3 | Only **one** engineering-governance source is reachable | **Two** are: `.claude/rules/**`, and `.specify/memory/constitution.md` via ten live skills (§4.3) | **NOT MET** | **Yes — B11-1** | Remove the ten `speckit-*` skills |
| A-4 | Functional authority is `implemented.md` | `90-functional-knowledge.md`; `implemented.md:12` | **MET** | No | — |
| A-5 | ADR governance self-contained, next number 0010 | §9 | **MET** | No | — |
| **Dependency removal** | | | | | |
| DR-1 | No active `.specify` dependency | Zero runtime reads; **but** ten live skills execute `.specify/scripts/**` and load the constitution | **NOT MET** | **Yes — B11-1** | Remove the ten skills |
| DR-2 | No active `specs/` dependency | Zero runtime reads. Residual: `README.md` and `.serena/memories/**` present it as authority; `D-11-1` / `D-11-3` content questions open | **PARTIALLY MET** | **Yes — B11-1** | Update C-1…C-7; resolve D-11-1, D-11-3 by comparison before deletion |
| DR-3 | No active `speckit-*` dependency | Ten skills tracked, registered and invocable | **NOT MET** | **Yes — B11-1** | Remove; update `test_guards.py:842-843` |
| DR-4 | No CI / build / hook invocation of Spec Kit | Zero matches in `.github/**`, `build/**`, `dev.sh`, `.claude/settings.json` | **MET** | No | — |
| **Development lifecycle** | | | | | |
| L-1 | Feature workflow expressible without Spec Kit | §12 — every step owned and named | **MET for Claude**; **NOT MET for a human via `README.md`** | **Yes — B11-1 (C-1)** | Update `README.md` |
| L-2 | Change gates defined, ordered, guarded | Four gates; `60-architecture-gates.md` §60.3; H2/H3/H5 wired | **MET** | No | — |
| L-3 | Testing governance complete | `40-testing.md` §40.1–§40.7 | **MET**, with **D-11-2** open | No | Compare the constitution's per-change-type test matrix against §40.5 before deletion |
| L-4 | Documentation conventions stated | `10-principles.md` C-3 Diátaxis, C-4 C4, C-5 README quickstart + ADR pointer | **MET** as policy; `README.md` content points the reader at retired authority | No (folded into B11-1) | Update `README.md`, preserving its quickstart and ADR pointer |
| L-5 | Functional-update procedure defined | `90-functional-knowledge.md`; `functional-update` skill | **MET** | No | — |
| **TS / Angular / Electron** | | | | | |
| T-1 | Governance scope for `apps/web`, `apps/desktop` decided | `22-web-typescript.md` §22.4 — three options, none chosen | **NOT MET** | **Yes — B11-2** | Human decision; ADR for options 2 and 3 |
| T-2 | Live TS/Electron gates preserved | `22-web-typescript.md` §22.3; `.github/workflows/{web,desktop}.yml` | **MET** | No | Not weakened by retirement — they are code |
| **Historical preservation** | | | | | |
| H-1 | ADR history `0001`…`0009` preserved | Tracked, unmodified | **MET** | No | Preserve; do not renumber or reword (`70-adr.md` §70.6) |
| H-2 | Migration records preserved | `phase-2`…`phase-10` + this document | **MET** | No | Preserve unchanged |
| H-3 | Architecture history preserved where appropriate | A1/A2/A3 untouched; the two non-authoritative architecture docs untouched | **MET** | No | Preserve; §11 |

---

## 15. Proposed retirement delta

**Proposed only. Nothing in this section is executed in Phase 11.** No path below was deleted,
moved or edited at `d15b59f`. Nothing is proposed for deletion because its name contains `spec`,
`task`, `plan` or `constitution`.

### 15.1 Must remove — proven retired Spec Kit mechanism

| Path | Reason | Dependency evidence | Replacement | Could deletion break governance? |
|---|---|---|---|---|
| `.claude/skills/speckit-analyze/SKILL.md` | Spec Kit mechanism installed into the Claude surface | `.specify/integrations/claude.manifest.json` records the install with a SHA-256 digest | `.claude/rules/**` + the four governance skills | **Yes, until A-2 is updated** — `test_guards.py:843` fails |
| `.claude/skills/speckit-checklist/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-clarify/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-constitution/SKILL.md` | as above; authors a competing governance source | as above | `70-adr.md`; `adr-author` | as above |
| `.claude/skills/speckit-converge/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-implement/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-plan/SKILL.md` | as above; loads `.specify/memory/constitution.md` as governance (line 62) | direct, quoted in §4.3 | as above | as above |
| `.claude/skills/speckit-specify/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-tasks/SKILL.md` | as above | as above | as above | as above |
| `.claude/skills/speckit-taskstoissues/SKILL.md` | as above | as above | as above | as above |
| `.specify/scripts/powershell/*.ps1` (6) | The executable Spec Kit mechanism; only callers are the ten skills | §5.2 — no other caller in 845 files | none needed | No, once the skills are gone |
| `.specify/templates/*.md` (5) | Templates for the retired authoring pipeline | consumed only by `.specify/scripts/**` and the ten skills | none needed | No |
| `.specify/workflows/**` (2), `.specify/integration.json`, `.specify/init-options.json`, `.specify/integrations/*.json` (2), `.specify/.gitignore` | Spec Kit state, registry and integration bookkeeping. `claude.manifest.json` exists solely to track the ten skills being removed | self-referential | none needed | No |

`.specify/memory/constitution.md` and `.specify/memory/.constitution-template.json` are **not**
listed here. They are **M-1** under §15.4, because their content is the subject of B11-2.

### 15.2 Must update — references with an established Claude replacement

| Path | Exact reference | Replacement | Could the update break governance? |
|---|---|---|---|
| `README.md:16-20` | The "Authoritative documents" table naming `Synthia-Platform-Specification.md`, `.specify/memory/constitution.md`, `specs/.../plan.md`, `specs/.../tasks.md` | The `CLAUDE.md` §3 authority hierarchy: A1/A2/A3; `.claude/rules/**`; `docs/functional/implemented.md`; `docs/adr/` | No — but C-5 (`10-principles.md` §10.5) requires the README to keep a quickstart and an ADR pointer; both exist today and must survive |
| `README.md:72` | `specs/  Specification, plan, tasks, contracts, checklists` | Drop or restate | No |
| `README.md:235` | `specs/.../tasks.md §Deferred` as the omissions register | `docs/functional/implemented.md` | No — **conditional on D-11-3** |
| `README.md:146, 224` | `(constitution Principle I)`, `(constitution §Non-functional commitments)` | The corresponding `.claude/rules/` citation | No |
| `.serena/memories/core.md:7-8, 29-30` | Constitution as engineering governance; `specs/.../{plan,tasks}.md` as realization/work; `.specify/` as templates & scripts | `CLAUDE.md`, `.claude/rules/**`, `docs/functional/implemented.md` | No — but it is a live assistant-instruction surface, so leaving it stale is worse than leaving it absent |
| `.serena/memories/task_completion.md:3, 14, 16` | Constitution §Quality gate; contract edits into `specs/.../contracts/`; constitution test-category matrix | `40-testing.md` §40.6 command table; `.github/workflows/contracts.yml`; `40-testing.md` §40.5 | No — **conditional on D-11-1 and D-11-2** |
| `.serena/memories/conventions.md:3`, `.serena/memories/web/core.md:1` | `(constitution)`, `(constitution VII)` | `10-principles.md` P-17; `22-web-typescript.md` §22.2 | No — **conditional on B11-2**, since the Electron citation's source text is what UD-1 governs |
| `CLAUDE.md` §10 | *"Retired Spec Kit artifacts are not authoritative"* — currently describes artifacts **in the tree** | Restate as a completed retirement: what was removed, what was preserved, and why the exclusion still matters for history | **Yes** — `test_guards.py:1107` matches on `"not authoritative"`, which occurs exactly once in `CLAUDE.md`. Update both together |
| `.claude/hooks/test_guards.py:842-843` | `check("Spec Kit skills still present", len(speckit) == 10)` | Invert to assert **no** `speckit-*` skill remains | **This is the governance change itself.** Not a weakened test: the assertion's subject is being retired by decision, and the replacement asserts a stronger, opposite invariant. `40-testing.md` §40.1 forbids deleting or loosening a test to make a change pass — this change must *tighten* it |
| `.claude/hooks/test_guards.py:1107` | `"not authoritative" in claude_text.lower()` | An assertion matching the rewritten §10 | As above |
| `00-authority.md` §00.4, `70-adr.md` §70.1, `90-functional-knowledge.md` §90.2, `adr-author/SKILL.md` | *"`.specify/**`, `specs/**` ... remain in the tree pending a later retirement phase"* | Restate in the past tense. **Keep the exclusion itself** — a preserved historical document must still be denied authority | Minor — `test_guards.py:514` asserts `70-adr.md` names `integrations-service-delta.md` and `ragcore-langgraph-flow.md`; that assertion is unrelated and must not be disturbed |

### 15.3 Must preserve — historical records

| Path | Why |
|---|---|
| `docs/adr/0001`…`0009` + `docs/adr/README.md` | `70-adr.md` §70.6 — never renumbered, reworded, retroactively restatused or "corrected". Three cite `specs/**`; that stays |
| `docs/migration/phase-2-authority-model.md`, `phase-2-coverage-matrix.md` | The authority model and coverage matrix the whole migration rests on |
| `docs/migration/phase-7-validation.md` | The validation record; holds the largest concentration of Spec Kit references, all historical |
| `docs/migration/phase-8-worktree-guard.md` | Worktree enforcement record |
| `docs/migration/phase-9-baseline-input.md` | **The baseline source of record**, including Appendix A.1 (the CF-1 amendment) and the malformed `BL-08` line that UD-4 concerns. `00-authority.md` §00.3 makes it the tiebreaker if a rule file is found to have lost a requirement |
| `docs/migration/phase-9-baseline-coverage.md` | The 167-requirement mapping, DV-1…DV-11, EG-1…EG-8, the UD/CF/D registers |
| `docs/migration/phase-10-baseline-reconciliation.md` | CF-1 closure, F-1, D-4 |
| `docs/migration/phase-11-retirement-readiness.md` | This document |
| `principles.yaml`, `dotnet.yaml`, `dotnet_lang.yaml`, `python.yaml`, `python_lang.yaml` | The migration sources and the §00.3 tiebreaker. **Not Spec Kit artifacts** |
| `docs/architecture/**` incl. the two non-authoritative files | §11 — untouched |
| `Synthia-Platform-Specification.md` | Named non-authoritative, but it is the architecture history the three authorities were drawn from. **Not a Spec Kit artifact** and outside the retirement target |

### 15.4 Must review manually

| # | Item | Question that must be answered first | Why Claude must not decide it |
|---|---|---|---|
| **M-1** | `.specify/memory/constitution.md` (968 lines) and `.constitution-template.json` | Does it hold requirements that exist nowhere else — specifically the **Angular/Electron baselines** (lines 191, 435-449, 558, 715-722) and the **per-change-type test-category matrix**? | This is **B11-2 / UD-1** and **D-11-2**. Under option 2 of §22.4 the content is a migration input and must be preserved before deletion. Deleting it first would destroy the input |
| **M-2** | `specs/001-platform-scaffold/contracts/**` (9 files) | Do they state a contract obligation absent from the generated OpenAPI under `build/contracts/**`? | **D-11-1**. A content comparison, not an inventory question. `ragcore/tests/contracts/test_api_surface.py` names them as the frozen contract in prose without reading them |
| **M-3** | `specs/001-platform-scaffold/tasks.md` §Deferred | Does it name an intentional omission that `implemented.md` does not classify? | **D-11-3**. `90-functional-knowledge.md` §90.2 forbids inferring or reconstructing this |
| **M-4** | `specs/001-platform-scaffold/{spec,plan,data-model,research,quickstart,contract-freeze,implementation-freeze}.md`, `stage-*-notes.md`, `checklists/**` | Keep as clearly-labelled history in place, relocate under `docs/migration/`, or remove? | A curation decision. All are dormant prose; none is read at runtime. Either answer satisfies the retirement target |
| **M-5** | ~35 source and CI files citing `constitution Principle ...` in comments and lint messages (`apps/desktop/**`, `apps/web/**`, `.github/workflows/{desktop,edge,integrations,ragcore}.yml`, `.gitignore`, `build/scripts/**`) | Re-cite to `.claude/rules/**`, or leave as historical provenance? | Touching ~35 files across four stacks for comment text is scope the retirement target does not require. The **gates themselves stay untouched**. The Electron/Angular subset is coupled to **B11-2** |
| **M-6** | 15 source files citing `specs/001-platform-scaffold/{tasks,plan,contracts}` in docstrings, comments and 501 messages (7 `ragcore/workers/**`, `integrations/workers/command_consumer.py`, `ragcore/src/ragcore/api/customer/sample_flows.py`, `ragcore/tests/contracts/test_api_surface.py`, `apps/desktop/src/main/endpoint-execution-boundary.ts`, `apps/web/.../primitives.ts`, `dotnet/.../SortSpec.cs`), plus `build/infra/apim/apis.json` and `build/infra/messaging/queues.json` | Re-cite or leave as provenance? Note `build/contracts/ragcore/customer.v1.openapi.json` is **generated** — its `specs/...` text comes from the `sample_flows.py` docstring and changes only if the docstring does | Editing a docstring changes a generated contract, which `.github/workflows/contracts.yml` diffs. Coupled to **M-2** |
| **M-7** | `docs/adr/README.md:31` OQ-01 row citing `spec.md §Dependencies` | Re-point, annotate as historical, or leave? | An index entry about an open question. `70-adr.md` §70.6 permits updating the index but not editing history; which this is depends on the answer to M-4 |
| **M-8** | `docs/current-implementation/file-map.md:253, 260` | Update with M-4, or retire the file | Non-authoritative under §00.4; its fate follows M-4 |
| **M-9** | `.dockerignore:86` `specs/` | Remove with the tree, or leave as a harmless no-op | Cosmetic |

---

## 16. Human decisions required

| # | Decision | Blocks retirement? | Instrument | The question |
|---|---|---|---|---|
| **HD-1** | **UD-1 / B-4** — TS/Angular/Electron governance scope: principles-only, a separately supplied baseline, or deliberately ungoverned | **YES** | Explicit confirmation (opt. 1) or ADR (opt. 2, 3), `70-adr.md` §70.2 B | Which option? And under option 2, must the constitution's Angular/Electron text be migrated **before** `.specify/**` is removed? |
| **HD-2** | **M-1 / D-11-2** — does the constitution hold any requirement that exists nowhere else? | **YES** (gates the deletion, not the decision) | Human content review | Is there anything in those 968 lines to migrate first? |
| **HD-3** | **M-2 / D-11-1** — do the nine frozen contract documents hold anything the generated OpenAPI does not? | **YES** (gates the deletion of `specs/**`) | Human content review | Safe to delete, or migrate first? |
| **HD-4** | **M-3 / D-11-3** — does `tasks.md §Deferred` name an omission `implemented.md` does not classify? | **YES** (gates the deletion of `specs/**`) | Human content review; then `functional-update` if a gap is found | Safe to delete, or update `implemented.md` first? |
| **HD-5** | **M-4** — disposition of the remaining `specs/**` prose: keep in place, relocate under `docs/migration/`, or remove | **No** (any answer satisfies the target) | Human curation | Which? |
| **HD-6** | **M-5 / M-6** — re-cite ~50 comment and message references, or leave as provenance | **No** | Human curation | Which, and is it in scope for the retirement change? |
| **HD-7** | Approval of the retirement change itself, including the two `test_guards.py` assertion inversions (A-2, A-3) | **YES** | Explicit approval, in-session, per `00-authority.md` §00.10 | Approve the delta as scoped? |
| **HD-8** | **UD-2, UD-4, UD-5, UD-6/CF-2, UD-7, D-1, D-3, D-4, F-1, OQ-5** | **No** — §13 | Various; see §13 | Independent of retirement, before or after |

**None of these decisions is made, inferred or pre-empted here.** `00-authority.md` §00.10:
approval and acceptance are never inferred — not from the task description, an accepted plan,
silence, a satisfied hook, or the session running unattended.

---

## 17. Blocking issues

### B11-1 — active Spec Kit dependency

```text
CLASSIFICATION: active Spec Kit dependency
```

Three surfaces, one cause: the repository still presents Spec Kit as a current mechanism.

1. **Ten live `speckit-*` skills** execute `.specify/scripts/powershell/*.ps1` and load
   `.specify/memory/constitution.md` as governance (§4.3, quoted). This gives an agent a **second**
   engineering-governance source, which `00-authority.md` §00.1 does not admit.
2. **`README.md:16-20`** names `.specify/memory/constitution.md` as *"Engineering governance — how
   software is built, tested, reviewed, secured"* and `specs/.../{plan,tasks}.md` as technical
   realization and executable work — all three named **non-authoritative** by `00-authority.md`
   §00.4 by exact path. `README.md` never mentions `CLAUDE.md` or `.claude/rules/`.
3. **`.serena/memories/{core,task_completion,conventions,web/core}.md`** repeat the same
   misdirection to a live assistant surface, and route contract changes into `specs/.../contracts/`.

**Resolvable by the retirement change itself** (§15.1, §15.2), together with the two
`test_guards.py` assertion updates. It is listed as blocking because it is unresolved **at
`d15b59f`**, and because until it is resolved the repository has two governance sources rather
than one.

### B11-2 — human decision required

```text
CLASSIFICATION: human decision required
```

**UD-1 / B-4.** §8. The retired constitution is the only in-repo prose stating Angular and Electron
engineering rules, and ~35 live files cite it by name as their rationale. Which of the three
documented options applies determines whether that content is a **migration input** (option 2,
changing the retirement order) or **superseded** (options 1 and 3). Claude does not choose, and
`22-web-typescript.md` §22.4 is unchanged by this phase.

### Not blocking, explicitly

"Not ready" does not rest on any non-blocking deviation. **CF-2 / UD-6**, **UD-2**,
**UD-4 / D-2**, **UD-5**, **UD-7 / EG-1…EG-8**, **D-1**, **D-3**, **D-4**, **F-1** and **OQ-5**
are **not** cited as blockers here. Phase 10 named CF-2 and the editorial defects as *further*
reasons retirement was closed; measured against the retirement target, they are not retirement
prerequisites. Each remains open, recorded and unresolved.

---

## 18. Non-blocking findings

| # | Finding | Type | Disposition |
|---|---|---|---|
| N-1 | ~35 files cite `constitution Principle ...` in comments and lint messages | Stale provenance in prose | **M-5** — gates unaffected; the Electron/Angular subset couples to B11-2 |
| N-2 | 15 source files and 2 infra JSON files cite `specs/001-platform-scaffold/**` in docstrings, comments and 501 messages | Stale provenance in prose; zero runtime reads | **M-6**; note the generated-contract coupling |
| N-3 | `docs/adr/0006`, `0008`, `0009` cite `specs/**` and `spec.md` | Historical, inside preserved ADRs | Preserve unchanged (`70-adr.md` §70.6) |
| N-4 | `docs/adr/README.md:31` OQ-01 cites `spec.md §Dependencies` | Index entry, ambiguous | **M-7** |
| N-5 | `docs/architecture/integrations-service-delta.md` carries the densest `specs/**` citation set outside the Spec Kit trees | Already non-authoritative | Untouched (§11) |
| N-6 | `docs/current-implementation/file-map.md:253, 260` describes `specs/**` | Non-authoritative | **M-8** |
| N-7 | `.dockerignore:86` excludes `specs/` from build context | Harmless before and after | **M-9** |
| N-8 | `.gitignore:1, 40` cite the constitution for build-artifact and secret rules | Stale citation; the rules restate `10-principles.md` P-27 and `80-security-ops.md` §80.3 | **M-5** |
| N-9 | The eight enforcement gaps EG-1…EG-8 remain open | Baseline enforcement | **UD-7**; honestly recorded in each owning rule; not a retirement prerequisite |
| N-10 | Eleven deviations DV-1…DV-11 remain open | Baseline deviations | Recorded in `phase-9-baseline-coverage.md` §8 and inline in the owning rules; preserved, not repaired |
| N-11 | F-1 and the two findings in `60-architecture-gates.md` §60.4 remain open | Architecture conformance | Reported, never reconciled (§60.4). Not retirement prerequisites |

---

## 19. Phase 12 readiness

Phase 11 performed the first five steps of the mandatory order:

```text
AUDIT                          done — §3, §4, §5
IDENTIFY ACTIVE DEPENDENCIES   done — §5.3 (A-1…A-3), §5.4 (C-1…C-8)
VERIFY REPLACEMENT             done — §6, §7, §9, §10, §11, §12
CLASSIFY HISTORICAL ARTIFACTS  done — §5.5, §15.3
IDENTIFY HUMAN DECISIONS       done — §16 (HD-1…HD-8)
RETIRE                         NOT PERFORMED
FINAL VALIDATION               NOT PERFORMED
```

### 19.1 Entry conditions for Phase 12

Phase 12 may begin when **all** of the following hold, in this order:

1. **HD-1 (UD-1 / B-4)** decided — confirmation for option 1, or an **Accepted** ADR for option 2
   or 3. Under option 2, the Angular/Electron content is migrated **before** any deletion.
2. **HD-2, HD-3, HD-4** answered — the three content comparisons (M-1, M-2, M-3). Anything found
   to exist only in Spec Kit is migrated to its authoritative home **first**; for functional
   behaviour that means the `functional-update` procedure, not an inline edit.
3. **HD-5, HD-6** answered — the curation scope of the retirement change is fixed, so it does not
   expand mid-change.
4. **HD-7** given — explicit in-session human approval of the delta, including the two
   `test_guards.py` assertion inversions.

### 19.2 Required Phase 12 ordering

```text
1. Migrate anything found to exist only in Spec Kit (HD-2/3/4), under its own gate
2. Update test_guards.py assertions :842-843 and :1107 to the inverted invariants
3. Update CLAUDE.md §10, 00-authority.md §00.4, 70-adr.md §70.1,
   90-functional-knowledge.md §90.2 and adr-author/SKILL.md to the past tense,
   keeping the exclusion itself
4. Update README.md and .serena/memories/**  (C-1 ... C-7)
5. Remove the ten speckit-* skills and .specify/**  (§15.1)
6. Apply the HD-5 disposition to specs/**
7. Re-run the full governance suite and every stack gate the change touches
8. Update docs/functional/implemented.md only if verified behaviour changed
```

Deletion is step 5, not step 1. **Deletion is not proof of retirement** — the audit is.

### 19.3 What this document does not do

- It does not retire, delete, move or edit any Spec Kit artifact.
- It does not resolve **UD-1, UD-2, UD-4, UD-5, UD-6 / CF-2, UD-7, OQ-5, D-1, D-2, D-3, D-4** or
  **F-1**, and does not infer a human decision for any of them.
- It does not choose among the three options in `22-web-typescript.md` §22.4, and does not invent
  a TypeScript, Angular or Electron baseline.
- It does not modify architecture, application code, configuration or any test.
- It does not rewrite `docs/functional/implemented.md`, and does not reconstruct information that
  exists only in a Spec Kit artifact.
- It does not make itself authority. It records an audit, and it authorizes nothing.

---

## 20. Final status

```text
PHASE 11 NOT READY FOR RETIREMENT

Blockers:
  B11-1   active Spec Kit dependency
          - ten live speckit-* skills executing .specify/scripts/** and loading
            .specify/memory/constitution.md as governance
          - README.md:16-20 naming the constitution and specs/** as current authority
          - .serena/memories/** repeating it to a live assistant surface
          Resolvable by the retirement change itself (§15.1, §15.2).

  B11-2   human decision required
          - UD-1 / B-4, TypeScript / Angular / Electron governance scope.
            The constitution is the only in-repo statement of the Angular and
            Electron rules, and ~35 live files cite it by name. The option chosen
            determines whether that content is a migration input or superseded.
            Not Claude's to choose.

Not cited as blockers: CF-2/UD-6, UD-2, UD-4/D-2, UD-5, UD-7, D-1, D-3, D-4,
F-1, OQ-5 - all open, all recorded, none a retirement prerequisite (§13).

Governance suite at d15b59f: 486/486 passed.
Spec Kit artifacts changed in this phase: none.
```
