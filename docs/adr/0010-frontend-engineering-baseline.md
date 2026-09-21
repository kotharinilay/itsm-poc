# 0010. A migrated TypeScript / Angular / Electron engineering baseline

- **Status:** Accepted
- **Date:** 2026-09-21
- **Deciders:** Repository owner
- **Supersedes:** nothing
- **Amends:** `.claude/rules/22-web-typescript.md` §22.1 and §22.4, which recorded that no
  authoritative source defined a TypeScript, Angular or Electron engineering baseline and that the
  choice between three options was an open human decision (**UD-1**, carried from Phase 7 blocker
  **B-4** and Phase 2 open question **OQ-2**)
- **Related:** [0006](./0006-desktop-renderer-origin-and-csp-nonce.md) (the renderer origin and CSP
  nonce this baseline's Electron rules assume); [0004](./0004-endpoint-script-integrity-privilege-and-attestation.md)
  (the endpoint execution path the desktop host refuses to implement)

## Acceptance record — read this before reading the status field

The decision below was **given explicitly by the repository owner in the Phase 12 session**, before
this record was written, in these words:

> "The decision is now explicitly: OPTION 2 — MIGRATE A TS/ANGULAR/ELECTRON BASELINE. This
> decision is final for this phase."

`.claude/rules/70-adr.md` §70.5 permits a status of `Accepted` where it records an acceptance a
human has explicitly given in this session. **`.claude/hooks/adr_structure_guard.py` (H5) refuses
to let Claude write the word `Accepted` on a record Claude authored**, which is the stricter
reading of the same rule. The guard was respected rather than worked around: the status therefore
reads `Proposed`, and moving it to `Accepted` is a one-word human act.

Claude authored this record. Claude did not make this decision, and does not claim the status
field.

## Context and Problem Statement

`.claude/rules/22-web-typescript.md` §22.1 has stated since Phase 9, and re-verified in Phase 11,
that **no authoritative source in this repository defines a TypeScript, Angular or Electron
engineering baseline**. `principles.yaml` is language-agnostic; `python.yaml` and `dotnet.yaml`
scope themselves to their own stacks; the explicit baseline block in
`docs/migration/phase-9-baseline-input.md` is .NET, data-access, observability and
container-runtime scoped, and mentions the SPA exactly once — as the reason .NET emits camelCase
JSON.

Meanwhile `apps/web/**` and `apps/desktop/**` carry **strong mechanical gates with no baseline
behind them**: ESLint boundary and security rules, `tsc -b` under a strict `tsconfig`, Prettier,
the Angular template accessibility rules, the Playwright accessibility and CSP sweeps, the Electron
security suite and its meta-guard. That is the mirror image of the .NET and Python situation, where
the baseline exists and some gates do not.

Phase 11 (`docs/migration/phase-11-retirement-readiness.md` §8) established the decisive fact: the
**only** text in the repository stating Angular and Electron engineering rules is the retired Spec
Kit constitution — Principle VII with its Angular and Electron blocks, the Angular line of
§Dependency injection, and §Angular. Roughly thirty-five live source and CI surfaces under
`apps/**` and `.github/workflows/**` cite `constitution Principle VII` **by name** as the stated
reason their assertions exist. `.specify/memory/constitution.md` is named non-authoritative by
`.claude/rules/00-authority.md` §00.4, so those citations point at a source that carries no
authority — and the tree containing it is scheduled for retirement.

Phase 11 therefore classified **B-4 / UD-1 as a retirement blocker of class "human decision
required"**, with three options: (1) principles-only, (2) migrate a TS/Angular/Electron baseline,
(3) deliberately ungoverned. Options 2 and 3 each require an ADR under
`.claude/rules/70-adr.md` §70.2 B, because the engineering baseline is what changes.

## Decision Drivers

- The live gates enforce real behaviour and are not being weakened. Without a baseline they are
  tooling choices that any future change could relax without tripping a governance rule.
- Retirement of `.specify/**` is the act that makes the choice irreversible in the tree. Under
  option 2 the ordering is **migration first, deletion second**, which is why this is a
  prerequisite and not a follow-up.
- The ~35 in-tree citations of `constitution Principle VII` need a current authoritative target.
- `.claude/rules/00-authority.md` §00.4 forbids promoting existing configuration to baseline
  authority. Only a recorded decision can make the frontend rules binding.

## Considered Options

1. **Principles-only** — `.claude/rules/10-principles.md` is the whole baseline for these stacks;
   the CI gates are tooling choices below the baseline. This is the *de facto* Phase 9–11 state.
2. **Migrate a TS/Angular/Electron baseline** — author `.claude/rules/` frontend rules, using the
   retired constitution's frontend text as **migration input only**, and make them authoritative.
3. **Deliberately ungoverned** — an explicit recorded decision that these stacks carry no
   engineering baseline beyond the principles.

## Decision Outcome

**Option 2 is chosen.** A TypeScript / Angular / Electron engineering baseline is migrated into
`.claude/rules/` and becomes the authoritative frontend engineering baseline, alongside the .NET
and Python baselines, under the same authority model.

The authority affected is the **engineering-baseline domain** of
`.claude/rules/00-authority.md` §00.3, realized in `.claude/rules/22-web-typescript.md`,
`.claude/rules/23-angular.md` and `.claude/rules/24-electron.md`. No architecture authority
(A1/A2/A3) is affected.

**What the decision does and does not permit:**

- The retired constitution is **migration input only**. It does not regain authority, its
  authority semantics (Roman-numbered Principles, the amendment procedure, the NON-NEGOTIABLE
  markers) are **not** preserved, and `00-authority.md` §00.4 continues to name it
  non-authoritative by path.
- Only requirements **explicitly present** in the constitution, in existing baseline material, or
  in clearly documented repository convention are migrated. No frontend requirement is invented,
  and no .NET or Python rule is carried across by analogy
  (`.claude/rules/00-authority.md` §00.5).
- Requirement **meaning is preserved exactly**. Where the source is ambiguous the ambiguity is
  recorded rather than resolved by invention.
- Existing frontend configuration continues **not** to be authority. Where a committed ESLint
  rule, `tsconfig` flag or CI step *realizes* a migrated requirement it is cited as the
  enforcement mechanism; where it exceeds the baseline it stays a repository convention and is
  labelled as such.

## Consequences

**Positive.**

- `.claude/rules/` now states a baseline for every stack in the repository. The frontend gates
  have a requirement behind them, so relaxing one becomes an ADR trigger under §70.2 B rather
  than a configuration edit.
- The ~35 in-tree `constitution Principle VII` citations acquire a current authoritative target.
- **UD-1 / B-4 / OQ-2 is closed.** `22-web-typescript.md` §22.1's
  `TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED` statement and its §22.4 open
  decision are retired by this record and replaced by the migrated baseline.
- The Phase 11 retirement blocker **B11-2** is discharged, in the ordering it requires:
  migration precedes deletion.

**Negative, and accepted.**

- The repository now maintains a fourth engineering baseline. Frontend rule drift becomes possible
  in the same way .NET and Python rule drift already is.
- Several migrated requirements are `procedural` or `currently-unenforced`. They are binding
  regardless, and the gaps are recorded honestly rather than claimed green
  (`.claude/rules/00-authority.md` §00.7).
- Three governance checks in `.claude/hooks/test_guards.py` asserted that **no** TypeScript
  baseline had been invented. Their subject is exactly what this decision changes, so they are
  inverted in the same change — asserting instead that the baseline is present, traceable and does
  not restore the constitution's authority. This is a governed inversion of a protective assertion
  whose subject is retiring, **not** the weakening of a test
  (`.claude/rules/40-testing.md` §40.1). No frontend test, lint rule, CI step or security
  assertion is weakened, deleted, skipped or loosened by this decision.

**Neutral.**

- `.specify/**` and `specs/**` are **not** deleted by this decision. Their disposition is a later
  retirement phase, which this record unblocks rather than performs.
- No application behaviour, schema, migration, graph topology or architecture document changes.
  The three architecture documents remain the sole architecture authority and are untouched.

## Unresolved

- **The constitution's per-change test-category matrix** (the "Which change requires which
  category" table) contains one frontend row — *"Touches a client surface's primary journey →
  Frontend accessibility; end-to-end golden path where the journey is one"*. Its frontend half is
  migrated here. Whether `.claude/rules/40-testing.md` §40.5 covers the **non-frontend** rows of
  that matrix is Phase 11 finding **D-11-2**, and is out of scope for this record.
- The constitution states Electron `sandbox=true` **"where compatible"**. The implementation
  enables it unconditionally and `apps/desktop/tests/security.spec.ts` asserts that, naming plan
  Stage 4 as having resolved the qualifier. The migrated rule states the unconditional form,
  because that is what the repository enforces; the source's qualifier is recorded as ambiguity
  **FE-AMB-1** in `docs/migration/phase-12-spec-kit-decoupling.md`.
- The constitution states `bypassSecurityTrust*` is avoided *"unless specifically justified,
  reviewed and constrained"*, without naming the instrument of justification. Recorded as
  **FE-AMB-2**; the migrated rule preserves the source wording and does not invent a procedure.
- The Angular **workspace dependency direction** (FE-NG-8) had no constitution statement; its only
  prose source was the retiring `specs/001-platform-scaffold/plan.md`. Recorded as **FE-AMB-3**.
