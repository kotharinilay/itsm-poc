# 22 — TypeScript / Angular / Electron

## Scope

**This file governs the frontend and desktop stacks:**

| Governs | Stack |
|---|---|
| `apps/web/**` | TypeScript / Angular (7 projects) |
| `apps/desktop/**` | TypeScript / Electron |
| Any future `.ts`/`.tsx` outside those trees | TypeScript |

It does **not** govern `dotnet/**` (`.claude/rules/20-dotnet.md`) or `ragcore/**` /
`integrations/**` (`.claude/rules/21-python.md`).

---

## 22.1 Status — read this first

```text
TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED
```

**No authoritative source in this repository defines a TypeScript, Angular or Electron engineering
baseline.** This was established in Phase 2, re-verified in Phase 7
(`docs/migration/phase-7-validation.md` §5.3) and verified again in Phase 9 against the actual
sources:

- `principles.yaml` is language-agnostic by construction and names no stack.
- `python.yaml` / `python_lang.yaml` scope themselves `language == python`.
- `dotnet.yaml` / `dotnet_lang.yaml` scope themselves `language in [dotnet, csharp]`.
- `docs/migration/phase-9-baseline-input.md` — the explicit baseline block, newly available for
  Phase 9 — is **entirely .NET, data-access, observability and container-runtime scoped**. It
  mentions the SPA client exactly once, as the *reason* .NET emits camelCase JSON (`BL-07`). That is
  a statement about the .NET contract, **not** a TypeScript rule.

**Therefore this file states only what an authoritative source actually establishes.** It does not
invent a frontend standard, and Phase 9 did not author one.

> **Do not manufacture TypeScript, Angular or Electron equivalents of .NET or Python rules.**
> `mypy --strict` does not become "`strict: true` in tsconfig"; Ruff `S` does not become
> "eslint-plugin-security"; `EnableNETAnalyzers` does not become an ESLint config. Concepts that
> look similar across stacks are not evidence of a requirement
> (`.claude/rules/00-authority.md` §00.5, Phase 9 brief §6).

## 22.2 What does apply — the repository-wide principles

`principles.yaml` declares itself language-independent, so **`.claude/rules/10-principles.md`
applies to `apps/web/**` and `apps/desktop/**` in full.** That is the governance these paths carry
today, and it is real governance, not a placeholder.

In particular, and without adding anything the source does not say:

- **P-17 least privilege** is repository-wide and reaches these stacks explicitly — renderer
  privileges, `contextIsolation`, `nodeIntegration`, preload surface, and the breadth of any token
  or API scope the client holds. `.claude/rules/10-principles.md` P-17 is binding here.
- **P-27 externalized configuration** — no environment-specific literal (URL, key, tenant, feature
  toggle) in frontend or desktop source.
- **P-29 logs as an event stream**, **P-30 no swallowed errors**, **P-31 deterministic resource
  release**, **P-11 fail fast**, **P-20 make illegal states unrepresentable** — all apply as stated.
- **C-1 Conventional Commits** and **C-2 SemVer** (`.claude/rules/10-principles.md` §10.5) apply to
  every commit in this repository, including commits that touch only these trees.
- **C-3 Diátaxis**, **C-4 C4** and **C-5 README quickstart + ADR pointer** apply to documentation
  for these stacks.

The **stack-specific mechanism** for meeting any of these — which ESLint rule, which `tsconfig`
flag, which Angular or Electron API — is exactly what no authoritative source defines. Choose a
mechanism that meets the principle; do not record the choice here as though it were baseline.

## 22.3 Existing gates — mechanism without a baseline

These stacks carry **strong mechanical gates that no baseline stands behind.** This is the mirror
image of the .NET and Python situation, where the baseline exists and some gates do not.

| Workflow | Failing steps today |
|---|---|
| `.github/workflows/web.yml` | `npx eslint .`, `npx prettier --check .`, `npx tsc -b`, `npm run build`, `npm test`, accessibility sweep (`test:a11y`), Content Security Policy check (`test:csp`) |
| `.github/workflows/desktop.yml` | `npm run typecheck`, `npm run lint`, Electron security suite (`vitest`), a guard verifying the security suite fails correctly (`build/scripts/verify-desktop-security-guard.sh`), `npm run build` |

```text
EXISTING IMPLEMENTATION / REPOSITORY CONVENTION — NOT BASELINE AUTHORITY
```

Per Phase 9 brief §7 Case C and `.claude/rules/00-authority.md` §00.4:

- **These configurations are evidence of what is, not authority for what should be.** The presence
  of an ESLint config, a `tsconfig` setting or an Electron security assertion does **not** make it a
  baseline rule, and it must not be promoted to one by being written into this file.
- **Equally, they are not to be weakened.** They are live gates protecting real behavior — notably
  the Electron security suite and the CSP check. Nothing in this phase relaxes them, and
  `.claude/rules/40-testing.md` §40.6 forbids weakening a test to make a change pass.
- Preserving them is not the same as ratifying them. Ratification is the human decision below.

## 22.4 The open decision

```text
NO AUTHORITATIVE EQUIVALENT — HUMAN DECISION REQUIRED
Affected stacks: TypeScript, Angular (apps/web), Electron (apps/desktop)
```

Carried forward as blocker **B-4** (`docs/migration/phase-7-validation.md` §16) and open question
**OQ-2** (`docs/migration/phase-2-authority-model.md`). Recorded in
`docs/migration/phase-9-baseline-coverage.md` §9 as **UD-1**.

The three candidate answers, unchanged and still a human's to choose:

1. **Principles-only** — `.claude/rules/10-principles.md` is the whole baseline for these stacks,
   and the existing CI gates are tooling choices below the baseline. This is the *de facto* state
   today.
2. **A separately supplied TS/Angular/Electron baseline** — a rule pack equivalent to
   `python.yaml` + `python_lang.yaml` is authored and supplied as a migration input, then migrated
   into this file by a later phase.
3. **Deliberately ungoverned** — an explicit, recorded decision that these stacks carry no
   engineering baseline beyond the principles.

Option 2 and option 3 both need an ADR (`.claude/rules/70-adr.md` §70.2 B). Option 1 needs an
explicit human confirmation that the *de facto* state is the intended one.

**Until that decision is made, Phase 9 asserts nothing further about these stacks.** This file is
deliberately short. It is not a stub awaiting filler — its shortness is the accurate report.
