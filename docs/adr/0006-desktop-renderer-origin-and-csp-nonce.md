# 0006. The desktop renderer origin: a privileged custom scheme, not `file://`

- **Status:** Accepted
- **Date:** 2026-09-16
- **Deciders:** Platform architecture owner
- **Resolves:** An ambiguity in plan Stage 4's navigation allow-list, and the `'unsafe-inline'`
  concession in the Stage 3 CSP baseline
- **Related:** [0004 — Endpoint script integrity, privilege and attestation](0004-endpoint-script-integrity-privilege-and-attestation.md)

## Context and Problem Statement

Plan Stage 4 states the navigation allow-list twice, and the two statements cannot both be read
literally.

The table names the permitted destinations:

| Destination | Why |
|---|---|
| The renderer's own bundle origin | The application itself |
| `https://{gateway-origin}` | The single platform origin (FR-SURF-017) |
| `https://login.microsoftonline.com` and the tenant authority | Interactive Entra sign-in |

The prose then says: *"Scheme matching is exact: `https:` and `wss:` only, never `http:`, `file:`
or a custom scheme."*

The renderer bundle ships with the application and is loaded from disk. Its origin is therefore
`file:`, a custom scheme, or a locally-bound HTTPS server — and the prose forbids the first two
while the table requires the origin to exist. A literal reading of both sentences leaves only a
local HTTPS listener, which means a bound port and a certificate on a customer-managed endpoint.

Separately, plan Stage 3's CSP baseline specifies `style-src 'self' 'nonce-{random}'`, with the
nonce delivered per response. A statically served bundle has no response to attach a nonce to, so
the obvious implementation loosens the directive to `'unsafe-inline'` — and Angular does inject
component styles as inline `<style>` elements at runtime, so the loosening would be load-bearing
rather than theoretical.

Both questions are about the same thing: **who serves the renderer document**.

## Decision Drivers

- Constitution Principle VII: `file://` is avoided "where a safer protocol strategy applies".
- Three controls in the Stage 4 scaffold do not merely degrade over `file://` — they stop working.
- A control that is present but inoperative is worse than an absent one, because its test still
  passes.
- Nothing may weaken the prose rule where it actually governs: the set of **remote** destinations
  the window may point at.
- The Stage 3 baseline treats a loosened directive as something that "states why in review". Not
  loosening it at all is better than justifying it.

## Decision Outcome

**The renderer bundle is served by the main process over `app://renderer`, a scheme registered as
standard and secure via `protocol.registerSchemesAsPrivileged`.** The navigation rules keep two
separate predicates, and the host mints a CSP nonce per document response.

### Why not `file://`

A `file://` document has an **opaque** origin. Three controls depend on it having a real one:

| Control | What breaks over `file://` |
|---|---|
| **CSP** | `'self'` matches nothing, so the policy the host attaches is enforced against an origin that can never satisfy it |
| **IPC sender validation** | `new URL('file:///x').origin` is the string `'null'`; there is no origin to allow-list, leaving only a path-prefix comparison against attacker-influenced input |
| **Gateway requests** | The browser sends `Origin: null`, which the platform cannot distinguish from any other opaque origin |

The first two are constitution Principle VII requirements — a restrictive CSP, and every IPC sender
validated. Serving over `file://` would leave both written down, tested, and not working.

### How the prose rule is honoured

`src/main/navigation.ts` keeps the remote allow-list and the application's own origin apart, and
never conflates them:

- **`isAllowedRemote`** — exact scheme match against `https:` and `wss:` only, then exact *origin*
  match (not hostname, not suffix) against the configured gateway, authority and realtime origins.
  Never `http:`, never `file:`, never a custom scheme. This is the rule the prose states, applied
  where the prose means it.
- **`isRendererOrigin`** — the application itself. Permitted for `will-navigate` so a client-side
  route survives a hard load.
- **`isExternalOpenAllowed`** — stricter than either: `https:` only, allow-listed origin only.
  The renderer origin can never reach `shell.openExternal`, and neither can `wss:`.

`setWindowOpenHandler` still returns `{ action: 'deny' }` for every destination without exception.

### The scheme's privileges

`standard: true` and `secure: true` are what give the origin its properties. `corsEnabled: true`
keeps the same-origin policy applying normally, `allowServiceWorkers: false` withholds a capability
nothing needs, and the scheme receives **no** universal access — it is an ordinary origin that
happens to be served from disk.

### The CSP nonce

Because the host serves the document, it can mint one. On every request for the entry document the
protocol handler generates a 128-bit CSPRNG nonce, stamps it onto `<app-root>` as `ngCspNonce` and
onto any `<style>` element already in the document, and returns the response with a
`Content-Security-Policy` header naming that nonce. Angular propagates `ngCspNonce` to every style
element it injects at runtime.

**`'unsafe-inline'` therefore appears in no directive**, including `style-src`. Inline `<script>`
is deliberately *not* nonced: `script-src` stays `'self'`, so an inline script is blocked, which is
the correct and loud outcome.

The entry document is the one response whose policy is set at its source rather than by the
`onHeadersReceived` interceptor, because the interceptor cannot know the nonce. Both are
main-process code; the renderer does not serve itself and still cannot weaken anything.

## Consequences

**Positive.** CSP, IPC sender validation and gateway `Origin` all work as written rather than
appearing to. The strict `style-src` the Stage 3 baseline asks for is achieved rather than
conceded. No port is bound and no local certificate is needed. The renderer origin is stable and
assertable, so `isSenderTrusted` is a real origin check.

**Negative / accepted.**

- A reader comparing this implementation against plan Stage 4's prose will see `app:` and must read
  this record to know why. That is the cost of the divergence, and it is why the record exists.
- The protocol handler is now on the path of every renderer asset request, including a rewrite of
  the entry document on each load. The cost is a file read and two regex replacements on one small
  document per navigation.
- Path containment inside the bundle becomes this scaffold's responsibility rather than the
  filesystem's. `resolveBundlePath` refuses traversal — including percent-encoded forms and NUL
  bytes — and is asserted directly, with the guard script proving the assertion fails when
  containment is removed.

## Unresolved

- **Angular's critical-CSS inlining** currently emits no `<style>` element for this bundle, so the
  `<style nonce>` path is covered by unit assertions rather than by the shipped document. If global
  styles grow, that path becomes live — it is implemented and tested, not deferred, but it has not
  yet been exercised end to end.
- **Whether the renderer should be served from an ASAR archive** rather than a directory once
  packaging lands. It changes how `resolveBundlePath` reads files, not whether it contains them.

## More Information

- Constitution Principle VII, Section 2 Electron standards.
- `specs/001-platform-scaffold/plan.md` Stage 3 (CSP baseline) and Stage 4 (navigation allow-list).
- `apps/desktop/src/main/renderer-protocol.ts`, `navigation.ts`, `csp.ts`.
- `specs/001-platform-scaffold/stage-4-notes.md`.
