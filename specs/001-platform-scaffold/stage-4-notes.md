# Stage 4 Implementation Notes

**Date**: 2026-09-16 · **Scope**: Phase 4 (T050–T056g) — the Electron desktop host. No endpoint
remediation, no script execution, no authorization logic, no business use case.

The host renders the Angular `desktop-renderer` bundle, applies a fixed set of security controls,
and answers four read-only IPC channels. It decides nothing.

**Verified end to end**: a real Electron process serves the renderer at `app://renderer/`, exposes
exactly the four contract members on `window.synthiaDesktop`, and leaves `ipcRenderer`, `require`
and `process` unreachable from the page. The CSP nonce reaches Angular through `ngCspNonce`, the
style element Angular injects carries it, styles apply, and the renderer logs zero CSP violations.
178 desktop tests and 18 renderer tests pass; the guard script flips sixteen controls in turn and
the suite catches every one.

---

## Three decisions worth reviewing

### 1. The renderer is served over `app://`, not `file://`

This is the one place the implementation departs from a literal reading of plan Stage 4.
**Recorded as [ADR-0006](../../docs/adr/0006-desktop-renderer-origin-and-csp-nonce.md)**, which is
the governing statement; the summary below is orientation.

Plan Stage 4 says scheme matching is exact — "`https:` and `wss:` only, never `http:`, `file:` or a
custom scheme" — and in the same section lists "the renderer's own bundle origin" as a permitted
destination. Those two sentences cannot both be satisfied literally: the bundle is local, so its
origin is `file:`, a custom scheme, or a local HTTPS server. The scheme sentence is about *remote*
destinations; the bundle is the application itself.

`file://` was rejected because three controls in this scaffold **do not function** over it. A
`file://` document has an opaque origin, so:

| Control | What breaks over `file://` |
|---|---|
| CSP | `'self'` matches nothing — the policy is enforced against an origin that can never satisfy it |
| IPC sender validation | `new URL('file:///x').origin` is the string `'null'`; there is no origin to allow-list, leaving only a path-prefix string comparison against attacker-influenced input |
| Gateway requests | The browser sends `Origin: null`, indistinguishable from any other opaque origin |

The constitution anticipates exactly this: `file://` is "avoided where a safer protocol strategy
applies" (Principle VII). So the bundle is served over `app://renderer`, registered as **standard**
and **secure** via `registerSchemesAsPrivileged`, giving the renderer a real, stable origin.

The plan's constraint is honoured where it governs. `navigation.ts` keeps two separate predicates:

- `isAllowedRemote` — `https:`/`wss:` only, exact origin match against the configured allow-list.
  Never `http:`, never `file:`, never a custom scheme.
- `isRendererOrigin` — the app itself. Permitted for `will-navigate`, and **never** passed to
  `shell.openExternal`, which is stricter still: `https:` only.

Reverting to `file://` is an ADR-0006 amendment, not a code change — switching silently disables
the three controls above while leaving their tests green.

ADR-0006 also records the **CSP nonce**, which is the same decision seen from the other side:
because the host serves the document, it can mint a per-response nonce, stamp it onto `<app-root>`
as `ngCspNonce`, and name it in the header. Angular propagates it to every style element it
injects, so **`'unsafe-inline'` appears in no directive at all**. Inline `<script>` is deliberately
not nonced — `script-src` stays `'self'`, so an inline script is blocked, loudly.

### 2. `sandbox: true` forced the preload to be a bundled CommonJS file

`tsc` alone cannot build this preload correctly, and the failure mode is silent.

A sandboxed preload is loaded by Electron's own CommonJS loader, not Node's. It cannot be ESM — and
this package is `"type": "module"`, so `tsc` output would be. Its `require` is a polyfill resolving
only a short list of built-ins, never a relative file — so importing `../ipc-contracts/index.js`
would fail at load.

Either mistake produces a preload that does not load, leaving `window.synthiaDesktop` undefined and
the bridge absent. Nothing throws. So:

- `tsconfig.json` **excludes** `src/preload`; `npm run build:preload` bundles it with esbuild to a
  single CommonJS file with only `electron` external.
- `tsconfig.preload.json` type-checks it separately, because esbuild strips types without checking
  them.
- `tests/bridge-surface.spec.ts` asserts the build configuration, since this is a correctness
  property that no compiler enforces.

### 3. Two boundaries are declared as data, and refuse

**The desktop session integration boundary** (`session-boundary.ts`) is a descriptor, not a session.
It reports that token custody is the renderer's, authority is the platform's, and the main process
persists nothing — and `'main'` is not a value either custody field can take. The main process holds
no token, observes no sign-in and answers no question about who the user is. Sign-in is interactive
against the Entra authority, in the renderer, over HTTPS.

**The endpoint execution boundary** (`endpoint-execution-boundary.ts`) declares the four bindings a
real instruction must carry — work item, catalogue entry, version, content hash — and then refuses.
`executeApprovedScript` and `verifyScriptBindings` throw unconditionally; there is no configuration
or argument that makes either proceed, and no IPC channel reaches them.

They are separate functions on purpose. When this path is eventually built, "a mismatch on any of
the four aborts before execution" must be a property of the code's structure rather than of a
reviewer's attention.

`EXECUTION_PRECONDITIONS` records what must hold first, including both ADR-0004 open items and
"server-side authority exists" — a *precondition the boundary checks it was given*, never a
question it answers.

---

## What the security suite covers

178 assertions across four files, all pure — no window is driven, so they run in CI on a machine
with no display.

| File | What it proves |
|---|---|
| `tests/security.spec.ts` | Every `webPreferences` switch; origin configuration validation; the navigation allow-list, including suffix-extended hosts and wrong ports; `shell.openExternal` being stricter than navigation; `setWindowOpenHandler` denying without exception; CSP contents, nonce minting and injection, and that the policy replaces rather than merges; both IPC checks; bundle path containment; permissions, certificate errors and forbidden launch switches |
| `tests/no-policy.spec.ts` | No authority in any channel or bridge member name; a source scan of `src/` (comments and strings stripped) for decision vocabulary, child-process/`eval` APIs, and any disabled switch; both boundaries refusing |
| `tests/bridge-surface.spec.ts` | Contract and handler table agree exactly; the preload exposes one global with exactly the contract's members, passes no arguments, and uses `ipcRenderer.invoke` only; the preload build stays sandbox-compatible |
| `tests/renderer-contract.spec.ts` | The Angular bridge declaration and the host's `BRIDGE_SURFACE` have not drifted — read as text, so no build dependency is created between the two deployables |

`build/scripts/verify-desktop-security-guard.sh` is the actual gate. It copies `apps/desktop` to a
scratch directory, flips sixteen controls one at a time — sandbox, `contextIsolation`,
`nodeIntegration`, `webSecurity`, insecure content, `webviewTag`, the navigable schemes, the
external-open scheme, `script-src`, `style-src`, `frame-ancestors`, sender validation, argument
validation, certificate trust, the endpoint boundary, path containment — and asserts the suite goes
red for each, then green when unmodified. It runs as a required check in `.github/workflows/desktop.yml`.

Two controls were given named constants (`TRUST_CERTIFICATE_ERRORS`, `IS_IMPLEMENTED`) purely so the
guard has something to flip. A control expressed only as a literal inside a function body is a
control the guard cannot exercise.

---

## Lint

`apps/desktop/eslint.config.js` covers a class of mistake the test suite cannot: an API that must
never appear anywhere in this package, on any code path, including one nobody has written yet.
`child_process` and `vm` are forbidden outright; so are `eval`, `new Function`, and the AST shapes
of every disabled security switch. The main process may not import `ipcRenderer` or `contextBridge`
at all.

It is deliberately **not** type-aware: the sources span three TypeScript programs and every rule is
syntactic, so a type-aware parser would add a fourth config to keep in sync and buy nothing. Type
errors are caught by `npm run typecheck`, which checks both programs properly.

The rules were verified by planting a file importing `node:child_process` with `sandbox: false`,
`webSecurity: false` and `nodeIntegration: true` — all four fired. `npm run lint` runs in CI.

## Out of scope, and still open

- **Phase 3 is not done.** `desktop-renderer` gets its bridge service and a shell (plan Stage 3's
  "adding only the desktop bridge service"). It is not yet composed from `customer-features`,
  `platform-core` or `design-system`, because those do not exist yet — T038–T049 remain open.
- **No endpoint remediation**, per plan Stage 4 non-goals and ADR-0004's unresolved open items.
- **The gateway and realtime origins default to `.invalid`**, which RFC 6761 guarantees cannot
  resolve. This is intended: an unconfigured build reaches nothing rather than reaching something.
  Real origins come from `SYNTHIA_GATEWAY_ORIGIN`, `SYNTHIA_REALTIME_ORIGIN` and
  `SYNTHIA_AUTHORITY_ORIGIN`, each validated at startup.
- **The `<style nonce>` path is not yet exercised by the shipped bundle.** Angular's critical-CSS
  inlining currently emits no `<style>` element, so that branch is covered by unit assertions rather
  than end to end. Implemented and tested, not deferred. See ADR-0006 §Unresolved.
- **Packaging is not addressed.** Whether the bundle is eventually served from an ASAR archive
  changes how `resolveBundlePath` reads files, not whether it contains them. ADR-0006 §Unresolved.
