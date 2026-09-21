---
paths:
  - "apps/web/**"
---

# 23 — Angular engineering rules

## Scope

**This file governs the Angular workspace only: `apps/web/**`.**

That workspace holds three applications — `customer-portal`, `staff-portal`, `desktop-renderer` —
and four libraries — `design-system`, `platform-core`, `customer-features`, `staff-features`.

`apps/web/projects/desktop-renderer` is an Angular application **and** the document the Electron
host loads. Both this file and `.claude/rules/24-electron.md` bear on it: this file governs it as
Angular code, and `24-electron.md` governs the host that serves it.

It does **not** govern `apps/desktop/**` (`.claude/rules/24-electron.md`), `dotnet/**`
(`.claude/rules/20-dotnet.md`) or `ragcore/**` / `integrations/**`
(`.claude/rules/21-python.md`).

`.claude/rules/22-web-typescript.md` (shared client rules and TypeScript) and
`.claude/rules/10-principles.md` (repository-wide principles) apply here **in addition** to
everything below. Neither is restated.

**Authority.** These requirements were migrated in Phase 12 under
`docs/adr/0010-frontend-engineering-baseline.md` from the **retired** Spec Kit constitution, which
is migration input and **not** authority (`.claude/rules/22-web-typescript.md` §22.1,
`.claude/rules/00-authority.md` §00.4). Full traceability:
`docs/migration/phase-12-spec-kit-decoupling.md`.

---

## 23.1 Structure and composition

### FE-NG-1 — Standalone components
**Components are standalone.** No `NgModule` is introduced to declare a component that can declare
its own dependencies.

*Source: `constitution#Angular` ("Standalone components") · Enforcement: partial — Angular 20
makes standalone the default, so a non-standalone component has to opt out explicitly; no lint
rule forbids that opt-out. The default is the gate, and it is a real one.*

### FE-NG-2 — Feature-oriented organization and file layout
- **Feature-oriented organization** — code is grouped by the feature it serves, not by technical
  kind.
- **Colocation** — the component, its template, its style and its spec sit together where
  appropriate.
- **kebab-case file naming.**
- **`.spec.ts`** for tests.

*Source: `constitution#Angular` · Enforcement: procedural — the workspace follows all four
(`projects/customer-features/src/lib/chat/chat-shell.{ts,html,css,spec.ts}` is the shape); none is
mechanically checked.*

### FE-NG-3 — Angular DI, and no global mutable state
**Use Angular dependency injection, `inject()` where appropriate, and cohesive services. No global
mutable state.**

*Source: `constitution#DependencyInjection` (Angular line), `constitution#Angular` ·
Enforcement: procedural. This is the Angular realization of
`.claude/rules/10-principles.md` P-26 (explicit injected dependencies, no service locator) and
P-28 (stateless services), which are repository-wide and are not restated here.*

### FE-NG-4 — Cross-cutting infrastructure is centralized, not repeated
**Authentication and token handling, API-client infrastructure, and realtime/SignalR
infrastructure are each centralized rather than repeated.**

In this workspace that place is `platform-core`, which FE-NG-8 makes the only library the feature
libraries and applications may reach for it.

*Source: `constitution#Angular` · Enforcement: partial — FE-NG-8's import rules prevent a feature
library from reaching around `platform-core` to another workspace project, but nothing prevents a
feature library from re-implementing the infrastructure locally. That half is review.*

### FE-NG-7 — No state-management framework without a requirement
**A state-management framework must not be adopted unless a requirement justifies it.**

*Source: `constitution#Angular` · Enforcement: currently-unenforced — no dependency check rejects
one. It is the Angular instance of `.claude/rules/10-principles.md` P-8 (no speculative
capability), and adopting one without a stated requirement is an ADR trigger under
`.claude/rules/70-adr.md` §70.2 B(6). Recorded as **EG-8**.*

### FE-NG-8 — The workspace dependency direction
**The workspace dependency direction is fixed, and an import against it is an error:**

```text
applications  →  customer-features | staff-features  →  platform-core  →  design-system
```

- `design-system` is the floor: accessible primitives only, no business logic, and no dependency
  on any other workspace project.
- `platform-core` may depend on `design-system` and on nothing else in the workspace.
- `customer-features` must not import `staff-features`, and vice versa. Neither imports an
  application.
- An application must not import another application. Shared code goes through a library.
- **`staff-portal` must not import `customer-features`** — the staff portal provides no facility
  to start a chat session, and that import is how the rule gets broken by accident.

*Source: **not the constitution.** The direction's only prose statement in this repository is
`specs/001-platform-scaffold/plan.md` §Dependency direction, which is a retiring, non-authoritative
artifact, and `apps/web/eslint.config.js`, which states it in full as executable configuration. It
is migrated here so the rule survives that tree's retirement with a current authoritative
statement, and because it is the Angular realization of `.claude/rules/10-principles.md` P-13 and
P-24. Recorded as **FE-AMB-3** in `docs/migration/phase-12-spec-kit-decoupling.md`: the
requirement is preserved, and the fact that its source was a retiring artifact rather than the
baseline is recorded rather than hidden.*
*Enforcement: mechanical — six `no-restricted-imports` blocks in `apps/web/eslint.config.js`, with
`npx eslint .` a failing step in `.github/workflows/web.yml`.*

---

## 23.2 Accessibility

### FE-NG-5 — WCAG 2.2 Level AA, on every surface
**Accessibility is mandatory — WCAG 2.2 Level AA across all three surfaces, with no best-effort
surface.**

The three surfaces are `customer-portal`, `staff-portal` and `desktop-renderer`. "No best-effort
surface" is part of the requirement: the desktop renderer is held to the same level as the two
browser portals.

*Source: `constitution#Angular` · Enforcement: mechanical — `angular.configs.templateAccessibility`
over `**/*.html` in `apps/web/eslint.config.js`, with `elements-content`,
`label-has-associated-control` and `no-autofocus` raised to `error`; plus the axe-based Playwright
sweep `npm run test:a11y`, a failing step in `.github/workflows/web.yml`.*

### FE-NG-6 — The project-supported test runner
**Use the current Angular testing defaults and the project-supported runner.**

*Source: `constitution#Angular` · Enforcement: mechanical — `npm test` runs Karma/Jasmine over
every project plus the Node-based architecture test, and is a failing step in
`.github/workflows/web.yml`. Changing the runner is a test-placement convention change and an ADR
trigger under `.claude/rules/70-adr.md` §70.2 B(6).*

> A frontend change that **touches a client surface's primary journey** owes a frontend
> accessibility test, and an end-to-end golden-path test where that journey is one.
> *Source: `constitution#WhichChangeRequiresWhichCategory`, frontend row. The non-frontend rows of
> that table are Phase 11 finding **D-11-2** and are not migrated here.*

---

## 23.3 Security — the Angular half of "no client is a security boundary"

`.claude/rules/22-web-typescript.md` FE-SH-1 states the root rule. These are its Angular
consequences, and none of them may be weakened by a convenience.

### FE-NG-9 — Role gating in the UI is convenience only
- **Backend authorization is authoritative.**
- **Route guards must not be treated as security boundaries.**
- **Presentation components must not implement authorization policy.**

*Source: `constitution#VII` (Angular block) · Enforcement: mechanical —
`apps/web/projects/platform-core/no-authz.spec.ts`, run by `npm run test:architecture` inside
`npm test`, reads the source of the three applications and the two feature libraries and fails on
authorization vocabulary. **Do not weaken or delete it** (`.claude/rules/40-testing.md` §40.1).*

### FE-NG-10 — CSP is supported, and sanitization is not optional
- **Content Security Policy must be supported.**
- **Angular's sanitization rules are followed.**
- **`bypassSecurityTrust*` is avoided unless specifically justified, reviewed and constrained.**

*Source: `constitution#VII` (Angular block) · Enforcement: mechanical — `no-restricted-properties`
on `DomSanitizer` in `apps/web/eslint.config.js`; the CSP hosting sweep `npm run test:csp`, a
failing step in `.github/workflows/web.yml`; and
`docs/adr/0009-portal-delivery-one-origin-per-browser-surface.md`, which fixes how the policy
reaches a browser as a response header with a per-response nonce.*

> **FE-AMB-2, open.** The source says `bypassSecurityTrust*` is avoided *"unless specifically
> justified, reviewed and constrained"* and **does not name the instrument** of that
> justification. The wording is preserved rather than resolved by invention. Note that the ESLint
> rule is absolute, so today any use requires an `eslint-disable` — which
> `.claude/rules/22-web-typescript.md` FE-SH-3 makes a suppression that must be scoped and
> justified. Recorded in `docs/migration/phase-12-spec-kit-decoupling.md`.

Secrets in browser code are `.claude/rules/22-web-typescript.md` FE-SH-2, which states the rule
once for both clients.

---

## 23.4 What this file does not do

- It does not restate `.claude/rules/22-web-typescript.md` or `.claude/rules/10-principles.md`.
- It does not govern the Electron host. That is `.claude/rules/24-electron.md`, even where the
  subject is the renderer document it serves.
- It does not make `apps/web/eslint.config.js`, `angular.json` or `tsconfig.json` authoritative.
  They realize the rules above; they do not establish them.
- It does not authorize weakening a lint rule, a test or a CI step to make an Angular change pass
  (`.claude/rules/40-testing.md` §40.1).
