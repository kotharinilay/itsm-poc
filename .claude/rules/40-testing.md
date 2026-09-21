# 40 — Testing policy

**Scope: repository-wide**, with per-stack sections where the baseline states a stack-specific
layout. This file owns the testing baseline. It does **not** restate the testing obligations that
the gate rules already own:

| Obligation | Owned by |
|---|---|
| Migration and persistence suites, single head, working `downgrade()` | `.claude/rules/50-database.md` §50.8 |
| Graph, checkpoint, governance, idempotency, authorization, isolation and architecture suites | `.claude/rules/30-langgraph.md` §30.9 |
| That an accepted ADR never licenses skipping a test | `.claude/rules/70-adr.md` §70.8 |
| That updating the functional record never substitutes for a gate | `.claude/rules/90-functional-knowledge.md` §90.10 |

Those are pointers, not duplicates. §40.6 below states the one prohibition that is common to all of
them, because it is the baseline's and applies to changes none of those rules govern.

---

## 40.1 The non-negotiable

**Never weaken a test to make a change pass.**

No deletion. No `skip`. No `xfail`. No loosened assertion. No narrowed fixture. No removed test
case. No broadened tolerance. No disabled suite, workflow step or job.

This holds regardless of what licensed the change — an approval, an accepted ADR, a green
requirement elsewhere, or a rule in this very baseline. If a test now fails, either the change is
wrong or the test encoded an invariant that is deliberately changing, **and the second of those is a
governance decision, not an edit** (`.claude/rules/70-adr.md` §70.2 B).

**A pre-existing violation exposed by a new rule is not a reason to delete the test that found it.**
It is a deviation to record (`.claude/rules/00-authority.md` §00.7).

*Source: `dotnet.yaml#P-PY-S3` / `python.yaml#P-PY-S3` suppression policy, and the testing
obligations of rules 30, 50, 70 and 90, which state this prohibition identically.*

## 40.2 .NET test projects

**Scope: `dotnet/tests/**`.**

### Layout and naming
- `tests/` sits **parallel to `src/`**.
- A test project is named `<Project>.Tests`.
- Test methods are named **`Method_State_Expected`**.

*Source: `dotnet.yaml#P-DN-2` · Enforcement: partial — the `tests/` ⇔ `src/` pairing is
structurally checkable and the repository follows it; the method-name convention is review-only, as
the source states*

### Identical strictness — no relaxed ruleset
**Test projects inherit exactly the same strictness as `src`.** The root
`dotnet/Directory.Build.props` applies to every project including `tests/` — the same S1…S4
switches — and **there is no per-test override.**

*Source: `dotnet.yaml#P-DN-3` · Enforcement: mechanical — `Directory.Build.props` is at the root of
`dotnet/` and detects test projects **by path**, so a new test project cannot accidentally opt out.
Test projects turn off only `GenerateDocumentationFile`, which is not a strictness switch.*

**The one documented relaxation** is `dotnet_diagnostic.CA1707.severity = none` scoped to
`[tests/**/*.cs]` — underscores in member names, so test method names read as sentences. It applies
to **naming only, never to a correctness analyzer**, and it is the only one. Adding a second is a
baseline change requiring an ADR (`.claude/rules/70-adr.md` §70.2 B).

## 40.3 Python test suites

**Scope: `ragcore/tests/**`, `integrations/tests/**`.**

- Tests live in a **`tests/` package**.
- The runner is **pytest**.
- Test files are named **`test_*.py`**.
- **Descriptive test names.**

*Source: `python.yaml#P-PY-2` · Enforcement: partial — `testpaths = ["tests"]` with
`--strict-markers` and `--strict-config` in both `pyproject.toml` files, and pytest is a failing CI
step in both workflows. As the source states: pytest's own discovery convention is not a failing
gate, and descriptive-name quality is review-only.*

`assert` is permitted in tests and banned elsewhere — `.claude/rules/21-python.md` PY-6. The
`"tests/**/*.py" = ["S101"]` per-file-ignore is the mechanism for that split, **not** a relaxation
of the suppression policy.

## 40.4 TypeScript / Angular / Electron

**Scope: `apps/web/**`, `apps/desktop/**`.**

Until Phase 12 this section recorded that no authoritative source defined a test layout or naming
convention for these stacks. `docs/adr/0010-frontend-engineering-baseline.md` migrated a frontend
baseline, so the obligations now have a source. They are stated where they belong and are **not**
duplicated here:

| Obligation | Owned by |
|---|---|
| The frontend quality gate — build, test, format, lint, strict type check, architecture rules | `.claude/rules/22-web-typescript.md` FE-SH-3 |
| `.spec.ts` naming and colocation in the Angular workspace | `.claude/rules/23-angular.md` FE-NG-2 |
| The project-supported Angular runner and current testing defaults | `.claude/rules/23-angular.md` FE-NG-6 |
| WCAG 2.2 AA on all three surfaces, and the a11y test a journey change owes | `.claude/rules/23-angular.md` FE-NG-5, FE-NG-6 |
| The Electron security suite and the assertions it carries | `.claude/rules/24-electron.md` §24.1–§24.5 |

The live gates — `npm test`, `npm run test:architecture`, the accessibility sweep, the CSP check,
the Electron security suite and its meta-guard — **are not weakened** (§40.1). What changed in
Phase 12 is that they now have a stated requirement behind them; the gates themselves are
untouched.

## 40.5 Test kinds the baseline requires by name

Several principles in `.claude/rules/10-principles.md` can only be discharged by a test, and the
source names which kind. These are obligations on the code that realizes the principle, not on this
file.

| Principle | Test the source requires |
|---|---|
| **P-3** substitutability | **One shared behavioral contract suite per abstraction, executed against every implementation.** The source is explicit that substitutability is a runtime property and that no structural proxy discharges it. |
| **P-21** idempotency | **Execute the operation two or more times with the same input and assert a single net effect** (one row, one side effect). The source is explicit that only an execution test discharges this. |
| **P-32** explicit contracts | A **structural** check that public operations verify their declared postconditions and expose an invariant check, **plus** an integration test exercising each operation against its contract across representative call sequences. |
| **P-11** fail fast | A structural assertion that boundary types and handlers carry entry-point guards for their preconditions. |
| **P-20** illegal states unrepresentable | A structural assertion that boundary DTOs are parsed into constrained domain types and that domain constructors reject invalid state. |
| **P-25** immutability | A structural assertion that domain value types expose no post-construction mutators. |
| **P-31** resource release | A structural assertion that types owning released resources expose and honor a disposal/close contract used within a bounded scope. |
| **P-30** no swallowed errors | An architecture assertion that no catch/except block is empty, comment-only, or discards an error-typed result. |
| **P-12** Law of Demeter | An architecture assertion that no method call navigates beyond its immediate collaborator. |
| **DN-19** no `goto` | A **custom Roslyn/structural check failing on `GotoStatementSyntax`**. The source states that review is explicitly *not* acceptable for this rule. |

Where one of these checks does not exist today it is recorded as an enforcement gap in
`docs/migration/phase-9-baseline-coverage.md` §5 — **not** silently downgraded to review, and **not**
implemented in this phase (Phase 9 brief §24).

## 40.6 Running the gates

| Stack | Command | Where it runs |
|---|---|---|
| Governance guards | `python3 .claude/hooks/test_guards.py` | local; it is the guard suite's own test |
| .NET | `dotnet build` (warnings are errors), `dotnet format --verify-no-changes`, `dotnet test` | `.github/workflows/dotnet.yml` |
| RagCore | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` | `.github/workflows/ragcore.yml` |
| RagCore integration | `uv run pytest -q -m integration` | `.github/workflows/migrations.yml`, `integrations.yml` |
| Integrations | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` | `.github/workflows/integrations.yml` |
| Web | `npx eslint .`, `npx prettier --check .`, `npx tsc -b`, `npm test`, a11y, CSP | `.github/workflows/web.yml` |
| Desktop | `npm run typecheck`, `npm run lint`, `npx vitest run`, the security-guard verifier | `.github/workflows/desktop.yml` |
| Boundaries | `build/scripts/check-boundaries.sh` | `.github/workflows/boundaries.yml` |
| Migrations | single head, upgrade from base, models-match-DDL, every downgrade | `.github/workflows/migrations.yml` |
| Contracts | generated OpenAPI diff | `.github/workflows/contracts.yml` |

A change runs the gates its paths touch. A change to `.claude/**` runs the governance guard suite.

## 40.7 What this file does not do

- It does not define the DB, LangGraph, ADR or functional gates (rules 50, 30, 70, 90).
- It does not authorize adding a new enforcement mechanism. Where a baseline rule needs a gate that
  does not exist, it is recorded as an `ENFORCEMENT GAP`, and building it is a separate,
  human-directed decision (Phase 9 brief §24).
- It does not make a passing suite evidence of conformance. A gate that does not fire proves nothing
  (`.claude/rules/00-authority.md` §00.4).
