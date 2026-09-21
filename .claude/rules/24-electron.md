---
paths:
  - "apps/desktop/**"
---

# 24 — Electron desktop-host engineering rules

## Scope

**This file governs the Electron desktop host only: `apps/desktop/**`.**

| Path | Holds |
|---|---|
| `apps/desktop/src/main/**` | the main process — window, CSP, navigation, IPC guard, renderer protocol, session boundary, the refusing endpoint-execution placeholder |
| `apps/desktop/src/preload/bridge.ts` | the one file permitted to touch `ipcRenderer`, captured in a closure |
| `apps/desktop/src/ipc-contracts/**` | the typed IPC surface both sides agree on |
| `apps/desktop/tests/**` | the security suite that asserts most of this file |

It does **not** govern `apps/web/**` (`.claude/rules/23-angular.md`) — including
`apps/web/projects/desktop-renderer`, which is an Angular application governed as Angular code
even though this host serves it.

`.claude/rules/22-web-typescript.md` (shared client rules and TypeScript) and
`.claude/rules/10-principles.md` (repository-wide principles) apply here **in addition** to
everything below. Neither is restated.

**Authority.** These requirements are stated here, authorized by
`docs/adr/0010-frontend-engineering-baseline.md` (Accepted). The ADR records the decision; this
file is the rule (`.claude/rules/22-web-typescript.md` §22.1, `.claude/rules/70-adr.md` §70.1).

---

## 24.1 The host decides nothing

`.claude/rules/22-web-typescript.md` FE-SH-1 states the root rule for every client. Its Electron
consequence is the strongest statement in this file:

### FE-EL-1 — No business authorization decision exists in the renderer or in the main process
**No business authorization decision exists in the renderer or in the main process.**

*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical —
`apps/desktop/tests/no-policy.spec.ts` asserts that no decision vocabulary appears in main or
preload code, that the IPC contract exposes no authority, that the session boundary persists no
state and returns a constant descriptor, and that no field carries identity, tenancy or a verdict.
**Do not weaken or delete that suite** (`.claude/rules/40-testing.md` §40.1).*

---

## 24.2 The mandatory webPreferences switches

### FE-EL-2 — nodeIntegration disabled, contextIsolation enabled, sandbox enabled
**`nodeIntegration` is disabled, `contextIsolation` is enabled, and the sandbox is enabled.**

*Origin: `ADR-0010#VII` (Electron block). The migrated wording qualified the third as
`sandbox=true` **"where compatible"**. This repository enables it **unconditionally**, and
`apps/desktop/tests/security.spec.ts` asserts that. The unconditional form is stated here because
it is what the repository enforces; the qualifier is registered as **FE-AMB-1** in
`docs/governance/open-items.md` §5a rather than silently dropped or silently kept.*
*Enforcement: mechanical — three `no-restricted-syntax` selectors in
`apps/desktop/eslint.config.js` fail on the literal value that would disable any of them, plus
`apps/desktop/tests/security.spec.ts`, which additionally asserts the switch object is frozen and
that the switches are applied after the preload path so no caller can override one.*

### FE-EL-3 — webSecurity is never disabled; insecure content is never allowed
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical — `no-restricted-syntax`
selectors for `webSecurity` false and `allowRunningInsecureContent` true, plus
`apps/desktop/tests/security.spec.ts`. The same suite also asserts `webviewTag` stays disabled — a
second, weaker embedding surface — which is this repository's own addition and is a repository
convention, not a migrated requirement.*

---

## 24.3 The bridge and IPC

### FE-EL-4 — A narrow contextBridge surface only
**Expose a narrow `contextBridge` surface. Raw `ipcRenderer` must never be exposed, and neither
may broad Electron or Node APIs.**

*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical — a `no-restricted-syntax`
selector fails on exposing `ipcRenderer` through `contextBridge.exposeInMainWorld`;
`no-restricted-imports` bars `ipcRenderer` and `contextBridge` from `src/main/**`; and
`apps/desktop/tests/bridge-surface.spec.ts` asserts the preload exposes exactly one global,
exactly the members the contract declares, uses `invoke` only and only with a contract channel,
and passes no argument through to the main process.*

### FE-EL-5 — Every IPC sender and every IPC argument is validated
**Every IPC sender and every IPC argument must be validated.** These are two distinct checks, and
neither substitutes for the other.

*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical —
`apps/desktop/src/main/ipc-guard.ts` is asserted by `apps/desktop/tests/security.spec.ts` to
refuse an untrusted sender even with valid arguments, to refuse invalid arguments even from a
trusted sender, to refuse an unknown channel, to refuse a subframe sender on the app origin, to be
the only way to reach a handler, and to leak no host configuration in a refusal message.*

---

## 24.4 Navigation, origins and transport

### FE-EL-6 — Navigation and new-window creation are restricted
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical —
`apps/desktop/src/main/navigation.ts` with an origin allow-list, and a `setWindowOpenHandler` that
`apps/desktop/tests/security.spec.ts` asserts denies **every** destination without exception, for
any input.*

### FE-EL-7 — Remote resources use HTTPS/WSS under a restrictive CSP
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical —
`apps/desktop/src/main/config.ts` requires HTTPS for the gateway and the authority and WSS for
realtime, defaults to an unresolvable reserved domain so an unconfigured build reaches nothing,
and freezes what it loaded; `apps/desktop/src/main/csp.ts` carries no unsafe-eval and no
unsafe-inline in any directive, narrows connect-src to exactly the configured origins, replaces
rather than merges a server-supplied policy, and enforces rather than reports. All asserted by
`apps/desktop/tests/security.spec.ts`. See
`docs/adr/0006-desktop-renderer-origin-and-csp-nonce.md`.*

### FE-EL-8 — shell.openExternal never receives an untrusted URL
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical —
`apps/desktop/tests/security.spec.ts` asserts it is **stricter** than navigation: HTTPS only, and
it never hands the renderer origin to the operating system.*

### FE-EL-9 — file:// is avoided where a safer protocol strategy applies
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical — the renderer is served
over the privileged `app://renderer` scheme
(`docs/adr/0006-desktop-renderer-origin-and-csp-nonce.md`,
`apps/desktop/src/main/renderer-protocol.ts`), asserted by
`apps/desktop/tests/security.spec.ts` to be registered as a standard, secure, CORS-enabled scheme
that stays contained against traversal and refuses another origin or another scheme.*

---

## 24.5 Execution

### FE-EL-10 — No remote code execution
**No remote or dynamic code execution in the host.**

*Origin: `ADR-0010#VII` (Electron block) · Enforcement: mechanical — `no-eval`,
`no-implied-eval` and `no-new-func` at `error`; `no-restricted-imports` bars `child_process`,
`node:child_process`, `vm` and `node:vm` across the whole package; `no-restricted-properties` bars
`process.binding`; and `apps/desktop/tests/no-policy.spec.ts` asserts the tree calls no
child-process, shell-execution or dynamic-evaluation API. The lint lists are deliberately
absolute: `apps/desktop/eslint.config.js` states that a genuine need for any of them is an
architecture change belonging in an ADR, not in an `eslint-disable` comment.*

### FE-EL-11 — The endpoint execution path
When an endpoint executes a script — **which nothing in this repository does today** — all of the
following hold:

1. Scripts are **fetched per execution** and must not be cached locally.
2. The instruction **binds work item, catalogue entry, version and content hash**.
3. **A mismatch on any of the four aborts before execution.**
4. **Script handling stays in the main process** and never reaches the renderer.
5. Scripts **run as the signed-in user** and must not run elevated.
6. **The endpoint executes only a versioned, predefined, approved script, and never decides
   whether an operation is permitted.**

*Origin: `ADR-0010#VII` (endpoint execution path) · Enforcement: partial — the path is
deferred in full by `docs/adr/0004-endpoint-script-integrity-privilege-and-attestation.md`.
`apps/desktop/src/main/endpoint-execution-boundary.ts` is a refusing placeholder, and
`apps/desktop/tests/no-policy.spec.ts` asserts it reports itself unimplemented, throws on both
execution and binding verification, **records the four bindings a real instruction must carry**,
names server-side authority as a precondition it does not evaluate, and is reachable from no IPC
channel. Items 2 and 6 are therefore asserted today; 1, 3, 4 and 5 become testable when the path
is built. Building it is an architecture change governed by `.claude/rules/70-adr.md`, not a
frontend change.*

The attestation half — a client result is a claim, not proof — is
`.claude/rules/22-web-typescript.md` FE-SH-4.

---

## 24.6 Runtime currency

### FE-EL-12 — Electron stays on a currently supported release
*Origin: `ADR-0010#VII` (Electron block) · Enforcement: currently-unenforced — no check
verifies the pinned Electron major against the upstream support window.
`apps/desktop/package.json` pins `electron: ^44.4.0`, and `npm audit --audit-level=high` in
`.github/workflows/security.yml` reports advisories but says nothing about supported-release
status. Recorded as **EG-9**; the rule is binding regardless.*

---

## 24.7 What this file does not do

- It does not restate `.claude/rules/22-web-typescript.md` or `.claude/rules/10-principles.md`.
- It does not govern the renderer as Angular code. That is `.claude/rules/23-angular.md`.
- It does not make `apps/desktop/eslint.config.js`, `tsconfig.json` or the Vitest suite
  authoritative. They realize the rules above; they do not establish them.
- It does not authorize weakening the security suite, its meta-guard
  (`build/scripts/verify-desktop-security-guard.sh`), a lint rule or a CI step to make a desktop
  change pass (`.claude/rules/40-testing.md` §40.1).
