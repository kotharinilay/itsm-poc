---
paths:
  - "apps/**"
---

# 22 — Frontend baseline: TypeScript and the shared client rules

## Scope

**This file governs every frontend and desktop path, and nothing else.**

| Governs | Stack |
|---|---|
| `apps/web/**` | TypeScript / Angular — one workspace, 3 applications, 4 libraries |
| `apps/desktop/**` | TypeScript / Electron — the desktop host |

It does **not** govern `dotnet/**` (`.claude/rules/20-dotnet.md`) or `ragcore/**` /
`integrations/**` (`.claude/rules/21-python.md`). Every TypeScript file tracked in this repository
lives under `apps/`, which is why `apps/**` is this file's whole scope.

Two narrower files sit below it and load only for their own stack:

| File | Governs |
|---|---|
| `.claude/rules/23-angular.md` | `apps/web/**` — the Angular workspace |
| `.claude/rules/24-electron.md` | `apps/desktop/**` — the Electron host |

**This file states what is genuinely common to both clients.** A rule that belongs to one stack is
stated there and is not duplicated here.

Repository-wide principles in `.claude/rules/10-principles.md` apply to `apps/**` **in addition**
to everything here. This file states the frontend mechanism; it never relaxes a principle
(`.claude/rules/00-authority.md` §00.5).

---

## 22.1 Status — this is now an authoritative baseline

```text
TYPESCRIPT / ANGULAR / ELECTRON BASELINE — MIGRATED AND AUTHORITATIVE
Instrument: docs/adr/0010-frontend-engineering-baseline.md
Closes: UD-1 (Phase 9) = B-4 (Phase 7) = OQ-2 (Phase 2) = B11-2 (Phase 11)
```

From Phase 2 through Phase 11 this file recorded that **no authoritative source defined a
TypeScript, Angular or Electron engineering baseline**, and its §22.4 recorded the open human
decision between three options. That decision was made in Phase 12: **option 2 — migrate a
baseline**. The record is `docs/adr/0010-frontend-engineering-baseline.md`; the migration is
`docs/migration/phase-12-spec-kit-decoupling.md`.

### Where these requirements came from, and what that does not mean

The migration input was the **retired Spec Kit constitution**, `.specify/memory/constitution.md`,
**deleted from the tree in Phase 16** and surviving only in git history —
specifically Principle VII with its Angular and Electron blocks, the Angular line of §Dependency
injection, §Angular, §Quality gate, §Review, and the frontend row of §"Which change requires which
category".

```text
.specify/memory/constitution.md IS MIGRATION INPUT. IT IS NOT AUTHORITY.
```

`.claude/rules/00-authority.md` §00.4 continues to name it non-authoritative **by path**, and
nothing here restores that authority. Its authority semantics — Roman-numbered Principles, the
amendment procedure, the NON-NEGOTIABLE markers, the governance sections — were deliberately
**not** carried across. What was carried across is the requirement text, with its meaning
preserved, re-identified under this repository's own `FE-*` identifiers.

**The requirement is now stated here. Cite this file, not the constitution.** Roughly thirty-five
source comments and lint messages under `apps/**` and `.github/workflows/**` still read
`constitution Principle VII`. Those are stale pointers to a live rule, not evidence of a live
dependency; `docs/migration/phase-12-spec-kit-decoupling.md` records them, and they are not
rewritten under this phase.

### What is still not baseline

The committed frontend tooling remains **evidence of what is, not authority for what should be**.
Where a committed ESLint rule, `tsconfig` flag or CI step *realizes* a requirement below, it is
named as that requirement's enforcement mechanism. Where committed tooling goes **beyond** any
migrated requirement it stays a repository convention and is labelled as one — it is not promoted
to baseline by appearing in this file.

**Traceability.** Every rule carries `Source:`. The full table is
`docs/migration/phase-12-spec-kit-decoupling.md`.

**Enforcement** vocabulary is the repository's own — `mechanical`, `partial`, `procedural`,
`currently-unenforced` — verified against `apps/web/eslint.config.js`,
`apps/desktop/eslint.config.js`, both `tsconfig.json` files, both `package.json` files,
`.github/workflows/web.yml` and `.github/workflows/desktop.yml`. A rule labelled
`currently-unenforced` is **still binding**; the gap is recorded, not an exemption.

---

## 22.2 Shared client rules

These hold for the browser portals and for the desktop host alike.

### FE-SH-1 — No client is a security boundary
**No client — the Angular portals, the Electron desktop, or any future surface — is a security
boundary. Every authorization, tenancy and policy decision is made server-side and re-verified
server-side.**

This is the root requirement that `23-angular.md` §23.3 and `24-electron.md` §24.1 each realize
for their own stack. It is stated once, here.

*Rationale, preserved from the source: clients run where the platform does not control them.
Anything a client decides is a decision an attacker can make instead.*

*Source: `constitution#VII` (opening) · Enforcement: partial —
`apps/web/projects/platform-core/no-authz.spec.ts` (`npm run test:architecture`) asserts that no
presentation project contains authorization vocabulary, and `apps/desktop/tests/no-policy.spec.ts`
asserts the same for the Electron main and preload code. Both are build-failing gates. The
server-side half is owned by A1 and by `.claude/rules/80-security-ops.md`, not by this file.*

### FE-SH-2 — No secret in client code
**No secret may exist in client code.** No credential, API key, connection string or token literal
— including in defaults, fixtures, sample configuration or comments.

*Source: `constitution#VII` (Angular block: "No secret may exist in browser code"). Applied to the
desktop renderer too, because the renderer **is** browser code:
`apps/web/projects/desktop-renderer` is an Angular application built from the same workspace and
loaded by the Electron host. That is the repository's own structure, not an extension of the
source. It also realizes `.claude/rules/10-principles.md` P-27 and
`.claude/rules/80-security-ops.md` §80.3, which reach `apps/**` independently.*
*Enforcement: partial — Gitleaks over the repository in `.github/workflows/security.yml`. No
TypeScript-specific credential-literal analyzer is bound; this is the frontend half of **EG-2**.*

### FE-SH-3 — The frontend quality gate
**No frontend change is complete unless all of the following hold:** the code builds; tests pass;
formatting passes; lint passes; strict type checking passes; architecture rules pass; and the
security and accessibility gates pass where relevant. **A change must not merge with new
suppressions.**

| Obligation | `apps/web` | `apps/desktop` |
|---|---|---|
| builds | `npm run build` | `npm run build` |
| tests pass | `npm test` | `npx vitest run` |
| formatting passes | `npx prettier --check .` | none configured — see DV-12 |
| lint passes | `npx eslint .` | `npm run lint` |
| strict type checking passes | `npx tsc -b --pretty` | `npm run typecheck` |
| architecture rules pass | `npm run test:architecture` | `apps/desktop/tests/no-policy.spec.ts` |
| security / accessibility | `npm run test:a11y`, `npm run test:csp` | `build/scripts/verify-desktop-security-guard.sh` |

*Source: `constitution#QualityGate`, `constitution#Review` · Enforcement: mechanical — every
command above is a failing step in `.github/workflows/web.yml` or `.github/workflows/desktop.yml`.
**One exception:** `apps/desktop` configures no formatter, so the "formatting passes" obligation
has no desktop mechanism. Recorded as deviation **DV-12**; the configuration is not changed here
(`.claude/rules/00-authority.md` §00.7).*

> "No new suppressions" is the frontend statement of what `.claude/rules/20-dotnet.md` DN-21 and
> `.claude/rules/21-python.md` §21.1 state for their stacks. **An `eslint-disable` comment is a
> suppression**: scope it narrowly and justify it, or do not add it. Adding a blanket or
> unjustified one is an ADR trigger under `.claude/rules/70-adr.md` §70.2 B(3).
> *Enforcement: procedural — no check counts ESLint suppressions. Recorded as **EG-7**.*

### FE-SH-4 — A client-reported result is a claim, not proof
**A result reported by a client is a claim, not proof.** A client-attested outcome must not be
presented as a confirmed resolution.

*Source: `constitution#VIII`, `constitution#VII` (endpoint execution path) · Enforcement:
not-applicable today — nothing executes on an endpoint
(`docs/adr/0004-endpoint-script-integrity-privilege-and-attestation.md`;
`apps/desktop/src/main/endpoint-execution-boundary.ts` is a refusing placeholder, asserted by
`apps/desktop/tests/no-policy.spec.ts`). The recording half — `server_confirmed`,
`client_attested`, `contradicted` — is backend behaviour and is **not** governed by this file.*

---

## 22.3 TypeScript rules

### FE-TS-1 — Strict TypeScript
**TypeScript runs in strict mode, and strict type checking is a failing gate.**

*Source: `constitution#Angular` ("strict TypeScript"), `constitution#QualityGate` ("strict type
checking passes") · Enforcement: mechanical — `apps/web/tsconfig.json` and
`apps/desktop/tsconfig.json` both set `"strict": true`; `npx tsc -b --pretty` and
`npm run typecheck` are failing CI steps.*

> **Beyond the baseline, recorded as repository convention rather than promoted to it:** both
> `tsconfig.json` files additionally set `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`,
> `noUnusedLocals`, `noUnusedParameters`, `noImplicitOverride` and `noFallthroughCasesInSwitch`;
> `apps/web` adds `noPropertyAccessFromIndexSignature` and `noImplicitReturns`, and its
> `angularCompilerOptions` set `strictTemplates`, `strictInjectionParameters` and
> `strictInputAccessModifiers`. Both ESLint configs set `@typescript-eslint/no-explicit-any` to
> `error`. **The migrated requirement is "strict TypeScript"; the above is how this repository
> currently meets and exceeds it.** Relaxing one of the extras is a convention change; relaxing
> `"strict": true` itself is an ADR trigger under `.claude/rules/70-adr.md` §70.2 B(5).

### FE-TS-2 — Typed API contracts
**Contracts crossing the client boundary are typed.** A request, response or IPC payload is
modelled as a TypeScript type, never consumed as `any` or as an untyped object.

*Source: `constitution#Angular` ("Typed API contracts") · Enforcement: partial —
`@typescript-eslint/no-explicit-any` at `error` in both configs removes the commonest escape, and
`apps/desktop/src/ipc-contracts/index.ts` types the IPC surface (asserted by
`apps/desktop/tests/bridge-surface.spec.ts` and `renderer-contract.spec.ts`). That a client type
matches the **published** contract is gated on the emitting side by
`.github/workflows/contracts.yml`, not on the consuming side; that half is review.*

### FE-TS-3 — The repository-wide principles, and their TypeScript mechanisms
This file does **not** restate `.claude/rules/10-principles.md`. It names the mechanism where the
frontend has one, so a principle is not enforced twice in two wordings:

| Principle | TypeScript mechanism in this repository |
|---|---|
| **P-29** logs as an event stream | `no-console` at `error` in both ESLint configs, allowing `warn`/`error` only, switched off for the two build-script paths whose whole output is a report |
| **P-30** no swallowed errors | review — no ESLint rule is bound for an empty `catch` |
| **P-27** externalized configuration | `apps/desktop/src/main/config.ts` reads and freezes host configuration; `apps/web/projects/customer-portal/src/app/platform.config.ts` binds the portal's. See also FE-SH-2 |
| **P-17** least privilege | `24-electron.md` §24.2–§24.3 for renderer privilege; `.claude/rules/80-security-ops.md` §80.2 for the operational surfaces |
| **P-8** no speculative capability | `23-angular.md` FE-NG-7 is the frontend instance the source states explicitly |
| **P-13 / P-24** separation, low coupling | `23-angular.md` FE-NG-8 (the workspace dependency direction) |
| **C-1 / C-2** Conventional Commits, SemVer | `.claude/rules/10-principles.md` §10.5 — repository-wide, including commits touching only `apps/**` |

*Source: `principles.yaml` via `.claude/rules/10-principles.md`; `constitution#Commits` for
C-1/C-2 · Enforcement: as stated per row.*

---

## 22.4 What this file does not do

- It does not restate the Angular rules (`.claude/rules/23-angular.md`) or the Electron rules
  (`.claude/rules/24-electron.md`).
- It does not restate `.claude/rules/10-principles.md`, which applies to `apps/**` in full.
- It does not define the DB, LangGraph, ADR or functional-record gates. Those are rules 50, 30, 70
  and 90, and they reach a frontend change exactly as they reach any other.
- It does not make any committed ESLint, `tsconfig`, Playwright or Vitest configuration
  authoritative. §22.1 says why.
- It does not authorize weakening a test, a lint rule or a CI step to make a frontend change pass
  (`.claude/rules/40-testing.md` §40.1).
