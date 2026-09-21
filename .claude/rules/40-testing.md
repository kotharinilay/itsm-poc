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

**This section is the *principle* axis only.** What a *change* owes is a separate obligation, stated
in §40.8 (the required categories TC-01…TC-15) and §40.9 (the per-change matrix CM-01…CM-12). A
change satisfies both axes; neither list is derived from, or substitutes for, the other.

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

---

## 40.8 Required test categories — TC-01 … TC-15

### The two testing axes

§40.5 above answers **"what does this *principle* owe?"**. The three sections below answer
**"what does this *change* owe?"**. They are different axes and neither derives from the other; a
change satisfies both or it is incomplete. Do not merge the two lists.

§40.8, §40.9 and §40.10 were **appended** rather than inserted, so that every existing section
number in this file stays stable and no cross-reference from another rule breaks.

*Authorized by `docs/adr/0011-required-test-categories-baseline.md` (Accepted). Migrated from
`.specify/memory/constitution.md` §Required test categories, §Which change requires which category
and §Coverage. **It is migration input. It is not authority.** Its non-authoritative
status under `.claude/rules/00-authority.md` §00.4 is unchanged by having been read. This file is
the testing-baseline authority; the constitution is not, and does not become so.*

### The fifteen categories

**All fifteen are required; none substitutes for another.**

| ID | Category | Proves |
|---|---|---|
| **TC-01** | Unit | Component behaviour in isolation |
| **TC-02** | Integration | Real collaborators, real database, real messaging |
| **TC-03** | Contract | Published API and message shapes, including between deployables |
| **TC-04** | Authorization | Every operation against every role set, including the empty intersection |
| **TC-05** | Tenant isolation | No path returns another organisation's data |
| **TC-06** | Retrieval isolation | The tenant filter cannot be evaded, including by crafted input |
| **TC-07** | Governance | Treatment comes from the catalogue and never from model output |
| **TC-08** | Approval | Binding, expiry, first-valid-verdict-wins, no synthesized verdict |
| **TC-09** | Idempotency | At-least-once delivery produces exactly one effect |
| **TC-10** | Concurrency | Concurrent claims and decisions resolve to one outcome |
| **TC-11** | Adapter | Provider behaviour stays behind its boundary |
| **TC-12** | Architecture dependency | Module boundaries, banned APIs, the no-cross-deployable-dependency rule |
| **TC-13** | Configuration validation | Options bind, validate and fail fast at start |
| **TC-14** | Security | The prohibitions stated by the baseline and the architecture are actually unreachable |
| **TC-15** | End-to-end golden path | A representative journey completes through every layer |

**A security or isolation fix without a failing-then-passing test is incomplete.**

In that order: the test
fails against the unfixed code and passes against the fixed code.
Its absence is not made good by any other category.

*Source: `constitution#Required test categories`, via ADR-0011 · Enforcement: **procedural** — the
suites exist and run (`ragcore/tests/`, `dotnet/tests/`, `integrations/tests/`; §40.6), but nothing
in this repository binds a diff to the categories it owes. Reviewed, not gated. See **EG-10** in
§40.9.*

## 40.9 Which change owes which category — CM-01 … CM-12

§40.8 says what each category *proves*. This section says when it is *owed*, so the obligation is
mechanical at review rather than a matter of judgement.

**A change matching several rows owes all of their categories.**
**TC-01 Unit is owed by every change and is therefore not repeated below.**

| ID | A change that… | Owes |
|---|---|---|
| **CM-01** | Adds or alters an API endpoint or message shape | TC-03 Contract; TC-04 Authorization |
| **CM-02** | Adds or alters an authorization rule, role set or accepted-role declaration | TC-04 Authorization; TC-14 Security |
| **CM-03** | Touches a query, repository, view or retrieval path | TC-05 Tenant isolation; TC-06 Retrieval isolation where retrieval is involved |
| **CM-04** | Adds or alters a catalogue entry, treatment policy or gate condition | TC-07 Governance; TC-04 Authorization |
| **CM-05** | Touches approval, consent, verdict or the resume path | TC-08 Approval; TC-10 Concurrency; TC-09 Idempotency |
| **CM-06** | Adds or alters an external side effect | TC-09 Idempotency; TC-11 Adapter |
| **CM-07** | Adds or alters a migration, table or published view | TC-02 Integration; TC-05 Tenant isolation; TC-12 Architecture dependency |
| **CM-08** | Adds or alters a module boundary, project reference or import | TC-12 Architecture dependency |
| **CM-09** | Adds or alters a configuration option or secret reference | TC-13 Configuration validation |
| **CM-10** | Touches an outbox, trigger, claim or worker | TC-09 Idempotency; TC-10 Concurrency |
| **CM-11** | Touches a client surface's primary journey | Frontend accessibility — owned by `.claude/rules/23-angular.md` **FE-NG-5** and **FE-NG-6**, not restated here; **plus** TC-15 End-to-end golden path where the journey is one |
| **CM-12** | Fixes a security or isolation defect | The relevant category above, **failing first, then passing** (§40.8) |

**CM-11 is an obligation of this matrix; the frontend *requirement* it points at is owned by
`.claude/rules/23-angular.md`.** The two are not duplicated
(`.claude/rules/00-authority.md` §00.5). The same division holds for the gate-owned obligations
listed at the head of this file — rules 30, 50, 70 and 90 own theirs, and this matrix does not
restate them.

*Source: `constitution#Which change requires which category`, via ADR-0011 · Enforcement:
**procedural**.*

> **ENFORCEMENT GAP EG-10.** No deterministic mechanism in this repository maps a changed file or a
> diff to the test categories §40.9 says it owes. The obligation is applied by a reviewer. This is
> recorded, **not** closed: ADR-0011 does not authorize building such a mechanism, and building one
> is a separate, human-directed decision (Phase 9 brief §24, `.claude/rules/40-testing.md` §40.7).
> A gap in the gate is never a reduction in the requirement.

## 40.10 Coverage

**No line- or branch-coverage threshold is set, and none gates a merge.** This is deliberate, not
an omission.

The gate is behavioural: each category in §40.8 is required, and every protection the baseline and
the architecture name as a hard failure must have a test that fails when the protection is removed.
A percentage target would be satisfiable without any of that, and would reward exercising code over
proving a guarantee.

Coverage **may** be measured and reported as information. It **must not** become a merge gate
without an accepted ADR amending this section — that is a change to a mandatory engineering
convention under `.claude/rules/70-adr.md` §70.2 B(6), and approval alone is not sufficient.

### The recorded exception — a gap, not a carve-out

Two hard failures —
**tenant context derived from an untrusted client field**, and **authorization bypass** —
have **no** failing-then-passing test at the backend, because the protection they tested
was deferred and not replaced (`docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md`,
open item **D-01**).

```text
The obligation in §40.8 is unchanged.  It is simply NOT MET for that pair.
```

**No test may be written that appears to meet it by asserting something weaker.** This is a
deviation recorded under `.claude/rules/00-authority.md` §00.7 — the requirement stands and the
implementation does not currently satisfy it. Closing it is a human decision: either the tests are
written, or the deferred protection is restored. Neither is done under this rule, and the deferred
architecture decision is not reopened here.

*Source: `constitution#Coverage`, via ADR-0011 · Enforcement: **procedural** — the prohibition is
honoured by the absence of a coverage gate in every workflow in §40.6; nothing mechanically
prevents one being added.*
