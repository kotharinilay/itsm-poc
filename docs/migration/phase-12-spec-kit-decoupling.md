# Phase 12 — Spec Kit decoupling and the frontend baseline migration

| | |
|---|---|
| **Phase** | 12 — decouple the live Claude Code surface from Spec Kit; migrate the frontend baseline |
| **Date** | 2026-09-21 |
| **Branch** | `speckit-to-claude` |
| **Starting revision** | `07d74c5` ("phase 11 readiness"), working tree clean |
| **Predecessor** | `docs/migration/phase-11-retirement-readiness.md` (committed, is `HEAD`) |
| **Scope** | The frontend engineering baseline; rule context-scoping; removal of the ten `speckit-*` skills; governance tests; README and Serena authority statements |
| **Not in scope** | Deleting `.specify/**` or `specs/**`; any application, schema, migration, graph or architecture change |

---

## 1. Objective

Close the two Phase 11 retirement blockers by (a) migrating a TypeScript / Angular / Electron
engineering baseline and making it authoritative under Claude Code governance, and (b) removing
every **active** Spec Kit dependency from the live Claude Code surface — while leaving `.specify/**`
and `specs/**` in the tree for a later retirement phase.

Secondary objective: reorganize `.claude/rules/` so instructions load when they are relevant
rather than every session, per current Claude Code guidance on path-scoped rules.

## 2. Starting state — validated before any change

| Check | Result |
|---|---|
| Branch | `speckit-to-claude` |
| Working tree | clean |
| Phase 11 committed | yes — `07d74c5 phase 11 readiness`, and it is `HEAD` |
| Phase 11 artifact present | yes — `docs/migration/phase-11-retirement-readiness.md` |
| Based on completed Phase 10 | yes — `d15b59f docs(governance): reconcile BL-10 migration ownership with Alembic (phase 10)` is `HEAD~1` |
| Unexpected application changes already present | none |
| Governance suite at start | 496 checks, all passing |

No reset, discard or history rewrite was performed at any point in this phase.

## 3. Decision — the TS / Angular / Electron baseline

```text
OPTION 2 — MIGRATE A TS/ANGULAR/ELECTRON BASELINE
```

Given explicitly by the repository owner in this session:

> "The decision is now explicitly: OPTION 2 — MIGRATE A TS/ANGULAR/ELECTRON BASELINE. This
> decision is final for this phase."

Recorded as `docs/adr/0010-frontend-engineering-baseline.md`. The record carries status
`Proposed`, **not** because acceptance is missing but because
`.claude/hooks/adr_structure_guard.py` (H5) refuses to let Claude write `Accepted` on a record it
authored. The guard was respected rather than circumvented. Moving the status to `Accepted` is a
one-word human act, and the record's own **Acceptance record** section says so and quotes the
decision verbatim.

The retired constitution `.specify/memory/constitution.md` was used as **migration input only**.
Its authority semantics were not preserved: no Roman-numbered Principles, no amendment procedure,
no `NON-NEGOTIABLE` markers, no governance sections. `.claude/rules/00-authority.md` §00.4
continues to name it non-authoritative by path, and Phase 12 strengthened rather than weakened
that statement.

## 4. Recorded ambiguities — preserved, not resolved by invention

| # | Ambiguity | What the source says | What was done |
|---|---|---|---|
| **FE-AMB-1** | Electron sandbox | `sandbox=true` **"where compatible"** | The rule (FE-EL-2) states the **unconditional** form, because that is what `apps/desktop/src/main/window.ts` sets and `apps/desktop/tests/security.spec.ts` asserts, naming plan Stage 4 as having resolved the qualifier. The source's qualifier is recorded here, neither silently dropped nor silently kept |
| **FE-AMB-2** | `bypassSecurityTrust*` | avoided "unless specifically justified, reviewed and constrained" — **the instrument of justification is not named** | FE-NG-10 preserves the source wording. No approval procedure was invented. Noted that the committed ESLint rule is absolute, so any use today requires a suppression, which FE-SH-3 already governs |
| **FE-AMB-3** | Angular workspace dependency direction | **Not in the constitution at all.** Its only prose statement is `specs/001-platform-scaffold/plan.md` §Dependency direction — a retiring, non-authoritative artifact — plus `apps/web/eslint.config.js`, which states it in full as executable configuration | Migrated as FE-NG-8 so the rule survives that tree's retirement with a current authoritative statement, and because it is the Angular realization of P-13/P-24. **The fact that its source was a retiring artifact rather than the baseline is recorded, not hidden** |

## 5. Source-to-rule traceability

Every migrated frontend requirement. `constitution#VII` is Principle VII, "No Client Is a Security
Boundary"; `constitution#Angular` is the §Angular engineering block; `constitution#DI` is the
Angular line of §Dependency injection; `constitution#QG` is §Quality gate + §Review;
`constitution#TC` is the frontend row of §"Which change requires which category".

| ID | Requirement | Source | Rule location | Scope | Enforcement | Status |
|---|---|---|---|---|---|---|
| **FE-SH-1** | No client is a security boundary; every authz/tenancy/policy decision is server-side and re-verified server-side | `constitution#VII` | `22-web-typescript.md` §22.2 | `apps/**` | partial — `no-authz.spec.ts`, `no-policy.spec.ts` | migrated |
| **FE-SH-2** | No secret in client code | `constitution#VII` (Angular block) + P-27 | `22-web-typescript.md` §22.2 | `apps/**` | partial — Gitleaks; EG-2 for the TS half | migrated, scope widened to the renderer on a stated repository fact |
| **FE-SH-3** | The frontend quality gate; no new suppressions | `constitution#QG` | `22-web-typescript.md` §22.2 | `apps/**` | mechanical, one gap (DV-12), suppressions procedural (EG-7) | migrated |
| **FE-SH-4** | A client-reported result is a claim, not proof | `constitution#VIII`, `#VII` | `22-web-typescript.md` §22.2 | `apps/**` | not-applicable today (ADR-0004) | migrated |
| **FE-TS-1** | Strict TypeScript | `constitution#Angular`, `#QG` | `22-web-typescript.md` §22.3 | `apps/**` | mechanical — `strict: true`, `tsc -b` in CI | migrated |
| **FE-TS-2** | Typed API contracts | `constitution#Angular` | `22-web-typescript.md` §22.3 | `apps/**` | partial | migrated |
| **FE-TS-3** | Repository-wide principles and their TypeScript mechanisms | `principles.yaml` via rule 10; `constitution#Commits` | `22-web-typescript.md` §22.3 | `apps/**` | per row | pointer, not a new requirement — stated to avoid enforcing a principle twice in two wordings |
| **FE-NG-1** | Standalone components | `constitution#Angular` | `23-angular.md` §23.1 | `apps/web/**` | partial — Angular 20 default | migrated |
| **FE-NG-2** | Feature-oriented organization, colocation, kebab-case, `.spec.ts` | `constitution#Angular` | `23-angular.md` §23.1 | `apps/web/**` | procedural | migrated |
| **FE-NG-3** | Angular DI, `inject()`, cohesive services, no global mutable state | `constitution#DI`, `#Angular` | `23-angular.md` §23.1 | `apps/web/**` | procedural | migrated |
| **FE-NG-4** | Auth/token, API-client and realtime infrastructure each centralized | `constitution#Angular` | `23-angular.md` §23.1 | `apps/web/**` | partial | migrated |
| **FE-NG-5** | WCAG 2.2 AA on all three surfaces, no best-effort surface | `constitution#Angular` | `23-angular.md` §23.2 | `apps/web/**` | mechanical — template a11y rules + axe sweep | migrated |
| **FE-NG-6** | Current Angular testing defaults and the project-supported runner; a journey change owes an a11y test and an e2e golden path | `constitution#Angular`, `#TC` | `23-angular.md` §23.2 | `apps/web/**` | mechanical | migrated |
| **FE-NG-7** | No state-management framework unless a requirement justifies it | `constitution#Angular` | `23-angular.md` §23.1 | `apps/web/**` | currently-unenforced (EG-8) | migrated |
| **FE-NG-8** | The workspace dependency direction | **not the constitution** — `plan.md` §Dependency direction + `eslint.config.js`; P-13/P-24 | `23-angular.md` §23.1 | `apps/web/**` | mechanical — six `no-restricted-imports` blocks | migrated, **FE-AMB-3** |
| **FE-NG-9** | Role gating is convenience only; route guards are not security boundaries; presentation components implement no authz policy | `constitution#VII` (Angular) | `23-angular.md` §23.3 | `apps/web/**` | mechanical — `no-authz.spec.ts` | migrated |
| **FE-NG-10** | CSP supported; Angular sanitization followed; `bypassSecurityTrust*` avoided unless justified | `constitution#VII` (Angular) | `23-angular.md` §23.3 | `apps/web/**` | mechanical — lint + `test:csp` + ADR-0009 | migrated, **FE-AMB-2** |
| **FE-EL-1** | No business authorization decision in the renderer or the main process | `constitution#VII` (Electron) | `24-electron.md` §24.1 | `apps/desktop/**` | mechanical — `no-policy.spec.ts` | migrated |
| **FE-EL-2** | `nodeIntegration=false`, `contextIsolation=true`, sandbox enabled | `constitution#VII` (Electron) | `24-electron.md` §24.2 | `apps/desktop/**` | mechanical — 3 lint selectors + security suite | migrated, **FE-AMB-1** |
| **FE-EL-3** | `webSecurity` never disabled; insecure content never allowed | `constitution#VII` (Electron) | `24-electron.md` §24.2 | `apps/desktop/**` | mechanical | migrated |
| **FE-EL-4** | Narrow `contextBridge` only; raw `ipcRenderer` never exposed; no broad Electron/Node APIs | `constitution#VII` (Electron) | `24-electron.md` §24.3 | `apps/desktop/**` | mechanical — lint selector + `bridge-surface.spec.ts` | migrated |
| **FE-EL-5** | Every IPC sender and every IPC argument validated — two distinct checks | `constitution#VII` (Electron) | `24-electron.md` §24.3 | `apps/desktop/**` | mechanical — `ipc-guard.ts` + security suite | migrated |
| **FE-EL-6** | Navigation and new-window creation restricted | `constitution#VII` (Electron) | `24-electron.md` §24.4 | `apps/desktop/**` | mechanical | migrated |
| **FE-EL-7** | Remote resources HTTPS/WSS under a restrictive CSP | `constitution#VII` (Electron) | `24-electron.md` §24.4 | `apps/desktop/**` | mechanical | migrated |
| **FE-EL-8** | `shell.openExternal` never receives an untrusted URL | `constitution#VII` (Electron) | `24-electron.md` §24.4 | `apps/desktop/**` | mechanical | migrated |
| **FE-EL-9** | `file://` avoided where a safer protocol strategy applies | `constitution#VII` (Electron) | `24-electron.md` §24.4 | `apps/desktop/**` | mechanical — `app://renderer`, ADR-0006 | migrated |
| **FE-EL-10** | No remote or dynamic code execution in the host | `constitution#VII` (Electron) | `24-electron.md` §24.5 | `apps/desktop/**` | mechanical — lint bans + `no-policy.spec.ts` | migrated |
| **FE-EL-11** | The endpoint execution path — six obligations | `constitution#VII` (endpoint) | `24-electron.md` §24.5 | `apps/desktop/**` | partial — deferred by ADR-0004; 2 of 6 asserted today | migrated |
| **FE-EL-12** | Electron stays on a currently supported release | `constitution#VII` (Electron) | `24-electron.md` §24.6 | `apps/desktop/**` | currently-unenforced (EG-9) | migrated |

**29 requirements migrated. None dropped.**

### 5.1 Constitution content deliberately NOT migrated

| Content | Classification |
|---|---|
| Principles I–VI, VIII–X | **Not frontend-related.** Owned by A1/A2/A3 and `.claude/rules/{00,10,30,50,60,70,80,90}` already |
| §.NET baseline, §Python baseline, §FastAPI architecture, §LangGraph and RagCore, §Model access, §Secrets, §Dependency injection (.NET and Python lines) | **Duplicate** — migrated in Phase 9 into rules 20, 21, 30, 50, 80 |
| §Required test categories (15 categories) and the **non-frontend** rows of §"Which change requires which category" | **Intentionally not migrated.** The frontend row is FE-NG-6. Whether rule 40 §40.5 covers the rest is Phase 11 finding **D-11-2** — an open content comparison this phase must not guess at |
| §Non-functional commitments, §Coverage, §Governance, §Amendment procedure, §Versioning policy, §Compliance review, §Recorded deviations (D-01) | **Historical / not frontend.** These are records about the constitution's own governance, whose authority semantics this phase explicitly does not preserve |
| §Commits and versioning | **Duplicate** — already `.claude/rules/10-principles.md` C-1/C-2 |
| §Development Workflow's "specification → plan → tasks → implementation" flow | **Unsupported going forward.** It describes the Spec Kit mechanism being retired; the Claude equivalent is the four gates in `CLAUDE.md` §§6–9 |

## 6. Path-scoping decisions

Principle applied: **a requirement loads at the narrowest scope sufficient to enforce it.**

| Rule | Scope | Why |
|---|---|---|
| `20-dotnet.md` | `dotnet/**` | its source pack declares `applied_when: language in [dotnet, csharp]` |
| `21-python.md` | `ragcore/**`, `integrations/**` | its source pack declares `applied_when: language == python` |
| `22-web-typescript.md` | `apps/**` | genuinely common to both clients; every tracked `.ts` file is under `apps/` |
| `23-angular.md` | `apps/web/**` | Angular only |
| `24-electron.md` | `apps/desktop/**` | Electron only |
| `00`, `10`, `40`, `60`, `80` | **unscoped** | repository-wide by their own scope statements; they apply to any change in any tree |
| `30`, `50`, `70`, `90` | **unscoped, deliberately** | these are the four **gates**, each defined as DETECT-**before**-implementation. Scoping a gate to the paths it governs would load it only *after* the moment it exists to catch. Recorded as a justified exception rather than left implicit |

Every glob was validated against the real tree. `test_guards.py` now asserts each scope prefix is
a real directory **and** matches tracked files, so an invented directory fails the suite.

**Rules were not split to increase file count.** `22-web-typescript.md` kept its filename so most
cross-references survived; only the genuinely stack-specific halves became `23` and `24`, each at
a narrower scope than a merged file could have had.

## 7. Rule-loading and context decisions

Before: **12 rule files, all loaded every session.**
After: **9 loaded every session; 5 load only when their tree is touched.**

| Working in | Loads |
|---|---|
| `dotnet/**` | 9 global + `20-dotnet.md` |
| `ragcore/**`, `integrations/**` | 9 global + `21-python.md` |
| `apps/web/**` | 9 global + `22-web-typescript.md` + `23-angular.md` |
| `apps/desktop/**` | 9 global + `22-web-typescript.md` + `24-electron.md` |
| anywhere else | 9 global |

`CLAUDE.md` gained six lines explaining the split and lost the duplicated Spec Kit paragraph; it
is **138 lines**, and the suite asserts it stays under 200 and never inlines the baseline. It
indexes the rule files by name and scope and does **not** import them, so no rule is forced into
every session by the root file.

**No requirement is stated in more than one layer.** Where a rule needed a neighbour's content it
names the file and section and stops — `40-testing.md` §40.4 became a pointer table rather than a
copy, and `22-web-typescript.md` FE-TS-3 names the TypeScript *mechanism* for a principle instead
of restating the principle.

## 8. Skill-versus-rule decisions

| Skill | Verdict |
|---|---|
| `adr-author`, `db-change`, `langgraph-change`, `functional-update` | **Retained.** Each is a genuine multi-step ordered procedure (detect → stop → describe → approve → implement → validate), invoked when a task needs it, and none is a static coding rule. None depends on `.specify/**` |
| the ten `speckit-*` skills | **Removed.** Each executed `.specify/scripts/powershell/*.ps1` and loaded `.specify/memory/constitution.md` as governance — the retired mechanism installed inside the Claude surface |

No new skill was created. Nothing in the frontend baseline is a procedure: it is a set of static
requirements, so it belongs in `.claude/rules/`, path-scoped, which is where it went.

`adr-author/SKILL.md` still names `.specify/**` and `specs/**` — **in a list of things that are
not sources**. That exclusion is required while the trees remain and is classified B, not A.

## 9. Spec Kit dependencies found

Classified with Phase 11's scheme (§5), re-verified at this revision.

| Class | Item | Where |
|---|---|---|
| **A — active dependency** | the ten `speckit-*` skills: live, invocable, executing `.specify/scripts/**` and loading the constitution as governance | `.claude/skills/speckit-*/SKILL.md` |
| **A — active dependency** | the governance suite **required** those ten skills to exist | `test_guards.py` — `check("Spec Kit skills still present", len(speckit) == 10)` |
| **B — current authority statement** | the README "Authoritative documents" table named the constitution as **engineering governance** and `specs/.../{plan,tasks}.md` as technical realization / executable work | `README.md` |
| **B — current authority statement** | Serena `core.md` named the constitution and `specs/**` as authoritative docs; `task_completion.md` routed contract edits into `specs/.../contracts/` and cited the constitution for the test-category matrix; `conventions.md` and `web/core.md` cited it as the governing source | `.serena/memories/**` |
| **B — current authority statement** | `CLAUDE.md` §10 described the `speckit-*` skills as present | `CLAUDE.md` |
| **B — current authority statement** | `00-authority.md` §00.4 described the `speckit-*` skills as remaining in the tree | `.claude/rules/00-authority.md` |
| **C — historical migration evidence** | every `docs/migration/phase-*.md` record | preserved unchanged |
| **D — historical ADR/reference** | ADRs 0006, 0008, 0009 cite `specs/**`; `docs/adr/README.md` OQ-01 cites `spec.md §Dependencies` | preserved unchanged |
| **E — ambiguous** | see §14 | recorded, not decided |

**The decisive negative result is unchanged from Phase 11 and was re-verified:** no build, test, CI
job, hook or application code path opens a Spec Kit file. Removing the ten skills broke nothing
executable.

## 10. Spec Kit dependencies removed

| Action | Detail |
|---|---|
| Deleted | `.claude/skills/speckit-{analyze,checklist,clarify,constitution,converge,implement,plan,specify,tasks,taskstoissues}/` — 10 skills, 10 tracked files |
| Inverted | the `test_guards.py` assertion that the ten skills exist → assertions that **none** exists |
| Rewritten | `CLAUDE.md` §10, `00-authority.md` §00.4, `README.md` authority model, four Serena memories, `docs/adr/README.md` header citation |
| Left in place, deliberately | `.specify/**` (21 files), `specs/**` (24 files), every migration record, ADRs 0001–0009, and every exclusionary mention that names Spec Kit **in order to deny it authority** |

After the change, the live Claude surface contains **no** reference to `.specify/scripts`,
`.specify/templates`, `.specify/extensions` or a `speckit-*` path, and `settings.json` invokes
nothing from Spec Kit. The suite asserts all of that, and additionally asserts that **wherever the
live surface still names Spec Kit, the same file denies it authority**.

## 11. README and Serena authority cleanup

`README.md` — the "Authoritative documents" table was replaced by three tables: architecture (the
three final documents), engineering/governance (`.claude/rules/`, `CLAUDE.md`, `.claude/skills/`)
and functional/history (`docs/functional/implemented.md`, `docs/adr/`). A blockquote names
`Synthia-Platform-Specification.md`, `.specify/**` and `specs/**` as history and **not** authority.
Three stale citations were repointed (`constitution Principle I` → A1; `constitution
§Non-functional commitments` → dropped; the `tasks.md §Deferred` pointer → `implemented.md`), and
the Layout block now describes `specs/` as a retired tree and adds `.claude/`.

`.serena/memories/**` — updated **only** where they actively misdirected toward the retired
authority model: `core.md` (authority list, the `.specify/` dir note, the P-6 citation),
`task_completion.md` (quality-gate citation, the contracts path, the test-category pointer),
`conventions.md` (heading citation) and `web/core.md` (heading citation, plus a pointer to the
three frontend rule files). Historical migration memories were **not** rewritten merely because
they mention Spec Kit, and `core.md` now states that `.serena/**` is itself not authority.

## 12. `.specify/**` and `specs/**` are intentionally retained

Neither tree was deleted, moved, or edited to hide a reference. `.specify/memory/constitution.md`
is **byte-identical** to its Phase 11 state — it was read as migration input and never written.
Their final disposition is a later retirement phase, after this decoupling has been validated in
use.

## 13. Validation results

`python3 .claude/hooks/test_guards.py` — **601 of 602 checks pass.**

| Validation | Result |
|---|---|
| Pre-existing governance checks | 496 before, 608 after. **492 retained unchanged and passing. 4 were inverted, not deleted** — 1 asserting the ten Spec Kit skills exist, 3 asserting no TS baseline had been invented. Each inversion's subject is exactly what this phase retires or decides, each is documented at the call site and in ADR-0010, and each replacement is harder to satisfy than silence. No check was deleted, skipped, loosened or narrowed (`.claude/rules/40-testing.md` §40.1) |
| New Spec Kit negative tests pass | yes — no `speckit-*` skill; exactly the four governance skills; no live file loads the mechanism; `settings.json` invokes nothing; every live mention denies authority |
| Path-scoped rules parse | yes — frontmatter terminated, `paths:` present and non-empty, one H1 after it |
| Rule paths match real directories and tracked files | yes — each scope prefix asserted to be a real directory **and** to match tracked files |
| No active `.claude/` dependency reads `.specify/**` | yes |
| No active Claude configuration invokes Spec Kit | yes |
| No current README authority statement points to Spec Kit | yes |
| No stale Serena memory remains as current authority | yes |
| Architecture authority unchanged | yes — A1/A2/A3 not modified; still the only three |
| Functional authority unchanged | yes — `docs/functional/implemented.md` not modified |
| ADR numbering/history unchanged | yes — 0001–0009 untouched; 0010 is the next number |
| DB / LangGraph gates unchanged | yes — rules 30 and 50 not modified; H2/H3/H5 not modified |
| Application behaviour | unchanged — no file under `dotnet/`, `ragcore/`, `integrations/`, `apps/`, `build/` or `.github/` was modified |
| `.specify/**`, `specs/**` | unchanged — `git diff` reports no modification |
| Mutation-style negative checks | the suite's existing worktree-planting harness (H2/H3/H5 fire on a planted violation and fall silent when it is removed) ran unchanged and passes |

**The one failing check, and why it is failing on purpose:**

```text
FAILED: exists: docs/adr/0010-frontend-engineering-baseline.md
```

Claude could not create the record from this session. H5 blocks a **shell** write to a new ADR
because it can only validate content carried by a whole-file `Write`, and the `Write` tool was
unavailable because the session's background-isolation guard requires a worktree, which this phase
was instructed not to create. Disabling that guard was refused as self-modification.

Rather than route around H5 — which is precisely the behaviour the governance model forbids — the
record was written to **`docs/migration/phase-12-adr-0010-staged.md`** and validated against
**H5's own `validate()` function**, which reports `VALID`. The check above is left **failing on
purpose** so the repository reports the true state: the rules cite an ADR, so the ADR must exist.

It passes the moment a human runs:

```bash
git mv docs/migration/phase-12-adr-0010-staged.md        docs/adr/0010-frontend-engineering-baseline.md
```

and, if they accept the decision, changes that record's `- **Status:** Proposed` to
`- **Status:** Accepted`. Both are human acts by design (`.claude/rules/70-adr.md` §70.3, §70.5).

## 14. Remaining non-blocking findings

| # | Finding | Status |
|---|---|---|
| **DV-12** (new) | `apps/desktop` configures no formatter, so FE-SH-3's "formatting passes" obligation has no desktop mechanism | recorded, configuration **not** changed |
| **EG-7** (new) | No check counts or justifies ESLint suppressions; FE-SH-3's "no new suppressions" is procedural | recorded |
| **EG-8** (new) | No dependency check rejects an Angular state-management framework (FE-NG-7) | recorded |
| **EG-9** (new) | No check verifies the pinned Electron major against the upstream support window (FE-EL-12) | recorded |
| **FE-AMB-1/2/3** | The three preserved ambiguities in §4 | recorded, not resolved |
| **D-11-1** | Whether `specs/.../contracts/**` holds anything the generated contracts do not | still open; Serena no longer routes contract edits there |
| **D-11-2** | Whether rule 40 §40.5 covers the constitution's non-frontend per-change test-category matrix | still open — a content comparison, not an inventory question |
| **D-11-3** | Whether `tasks.md §Deferred` and `implemented.md` describe the same set of omissions | still open; README now points at `implemented.md` |
| **~35 stale citations** | Source comments and lint messages under `apps/**` and `.github/workflows/**` reading `constitution Principle VII` | **class E — not decided here.** They are now stale pointers to a live rule. Repointing them touches ~35 application and CI files, which is an application change this governance phase must not make. Recommended for Phase 13 |
| **OQ-01 pointer** | `docs/adr/README.md` cites `Specification §40; spec.md §Dependencies` | **class E** — historical context for an open question, left for manual human review as Phase 11 §5.4 C-8 directed |

## 15. Blockers still remaining for final retirement

| # | Blocker | Owner |
|---|---|---|
| **B12-1** | `docs/adr/0010-frontend-engineering-baseline.md` is not on disk, and its status is `Proposed`. The frontend rules cite it. **Two one-line human acts**: `git mv docs/migration/phase-12-adr-0010-staged.md docs/adr/0010-frontend-engineering-baseline.md`, then set the status to `Accepted` | human |
| **B12-2** | ~35 source and CI surfaces under `apps/**` and `.github/workflows/**` cite `constitution Principle VII` by name. They break no build, but on the day `.specify/**` is deleted they become dangling citations in live code | Phase 13 |
| **B12-3** | **D-11-1** and **D-11-3** are content comparisons that must be performed before `specs/**` is deleted: does anything in `specs/.../contracts/**` or `tasks.md §Deferred` exist nowhere else? | Phase 13 |
| **B12-4** | **D-11-2** — whether the constitution's non-frontend per-change test-category matrix is covered by rule 40 §40.5. If it is not, the missing obligation disappears with the file | Phase 13 |

**This phase does not claim final Spec Kit retirement.** It removes the *active* dependency and
supplies the replacement text that retirement would otherwise destroy. Deletion remains a separate,
later, human-directed act.

## 16. Is B11-1 closed?

```text
B11-1 — CLOSED, subject to B12-1.
```

Phase 11 defined B11-1 as: the README and Serena memories declaring Spec Kit artifacts **current
authority**, and the ten `speckit-*` skills being **live, invocable** Claude skills that execute
`.specify/scripts/**` and load the constitution as governance.

- The ten skills are deleted; the suite fails if any returns.
- The README authority model names the three architecture documents, `.claude/rules/`,
  `.claude/skills/`, `docs/functional/implemented.md` and `docs/adr/`, and explicitly denies
  Spec Kit authority.
- The four misdirecting Serena memories are corrected.
- `CLAUDE.md` §10 and `00-authority.md` §00.4 no longer describe the skills as present.
- The suite asserts, deterministically, that no live Claude file loads the mechanism, that
  `settings.json` invokes nothing from it, and that every remaining mention denies it authority.

"Subject to B12-1" because the governance suite is not fully green until the ADR record lands.

## 17. Is B11-2 / UD-1 closed?

```text
B11-2 = B-4 = UD-1 = OQ-2 — CLOSED as a decision; CLOSED in the rules; RECORD PENDING.
```

- **The decision is made** — option 2, given explicitly by the repository owner in this session
  and quoted verbatim in the ADR and in §3 above.
- **The rules carry it** — 29 requirements across `22-web-typescript.md`, `23-angular.md` and
  `24-electron.md`, each with a `Source:` line, an honest enforcement label, and a traced entry in
  §5. `22-web-typescript.md` §22.1 now reads `MIGRATED AND AUTHORITATIVE`; the
  `TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED` statement and the §22.4 open
  decision are gone, and the suite fails if either returns.
- **The record is pending** — see B12-1. Until it is placed and accepted, the instrument that
  authorizes the baseline exists as validated staged content rather than as a committed record.

The constitution did **not** regain authority. `00-authority.md` §00.4 still names it
non-authoritative by path, and the suite asserts the rules state it is migration input only.

## 18. Recommended next phase

**Phase 13 — citation repointing and content-comparison closure, then retirement.** In this order:

1. **Human, first:** place `docs/adr/0010-frontend-engineering-baseline.md` and set its status to
   `Accepted` (or reject the record, in which case Phase 12's rule changes must be reverted as a
   unit). Re-run `python3 .claude/hooks/test_guards.py` and confirm 602/602.
2. **Repoint the ~35 stale citations** (B12-2) from `constitution Principle VII` to the
   `.claude/rules/{22,23,24}` requirement ids. This is an application/CI comment change, so it
   needs its own approval; it changes no behaviour and no assertion.
3. **Close D-11-1, D-11-2 and D-11-3** (B12-3, B12-4) by content comparison. Each may produce a
   migration of its own, which must precede deletion.
4. **Only then, Phase 14 — deletion** of `.specify/**` and `specs/**`, with `.dockerignore` and
   any remaining descriptive references updated in the same change.

**Do not delete `.specify/**` or `specs/**` before step 3 completes.** Step 1 exists first because
the repository currently cites an ADR that is not on disk.
