# Synthia web workspace

Three client surfaces and four libraries (plan Stage 3). **This is a scaffold**: the structure,
contracts and infrastructure are real, and no business workflow is implemented.

## Layout

| Project             | Kind | What it is                                                                     |
| ------------------- | ---- | ------------------------------------------------------------------------------ |
| `customer-portal`   | app  | Customer surface (spec FR-SURF-001)                                            |
| `desktop-renderer`  | app  | Customer desktop surface, rendered by the Electron host                        |
| `staff-portal`      | app  | Staff surface — works on other people's sessions                               |
| `customer-features` | lib  | Customer feature shells: chat, session, consent, hand-off                      |
| `staff-features`    | lib  | Staff feature shells: queue, take-over, reporting                              |
| `platform-core`     | lib  | Typed API contracts and clients, auth, correlation, realtime, browser security |
| `design-system`     | lib  | Accessible primitives and the loading/empty/failure state vocabulary           |

### Dependency direction

```text
apps → customer-features | staff-features → platform-core → design-system
```

Anything not drawn there is prohibited, and `eslint.config.js` fails the build on a violating
import rather than leaving it to review. `customer-features` and `staff-features` never import each
other; no application imports another application; the staff portal cannot import
`customer-features` at all.

## Commands

```bash
npm run build          # four libraries, then all three applications
npm test               # unit specs (Karma) + the architecture scan
npm run lint           # ESLint, including the library-boundary rules
npm run typecheck      # tsc -b across every project
npm run format:check   # Prettier

npm run e2e:install    # once — downloads the Chromium Playwright uses
npm run e2e            # axe-core WCAG 2.2 A/AA sweep across all three surfaces
```

Karma needs a Chrome binary. Set `CHROME_BIN` if it is not on the default path.

## The rules this scaffold is built around

**Backend authorization is authoritative.** No client surface makes an authorization, tenancy or
policy decision (spec FR-SURF-004). Role gating here is presentation convenience: it avoids showing
somebody a menu item the platform will refuse. A route guard is not a security boundary — the person
holds the browser. Deleting every role check in this workspace would change nothing about what
anyone can actually do. `projects/platform-core/no-authz.spec.ts` scans the source to keep it that
way, and fails when a violation is planted.

**Roles have no hierarchy.** `technician`, `senior_technician` and `administrator` are independent
capabilities; `administrator` does not imply `technician`. Evaluation is set intersection, and an
empty intersection denies. Anything that sorts, ranks or compares roles is a defect — asserted here,
in `dotnet/tests/.../RoleIntersectionTests.cs` and in `ragcore/tests/unit/test_roles.py`
independently.

**One gateway.** A client addresses the platform through a single origin (FR-SURF-017). Which
backend serves an operation is not a client concern, so `PlatformApiClient` takes a path and there
is no way to express a second origin through it.

**No secret in browser code.** A browser cannot keep one — anything shipped to the page is readable
by whoever loads the page. `assertConfigCarriesNoSecret` fails at bootstrap rather than in review.

**CSP is a response header, never a `<meta>` tag.** A policy in the document can be stripped by
injected markup, and `frame-ancestors` is ignored there entirely. `buildCspHeader` produces the
value; the hosting tier sets it. `script-src` carries no `unsafe-inline` and no `unsafe-eval`, which
is why the build is AOT.

**Angular sanitization stands.** `bypassSecurityTrust*` is absent, enforced by ESLint and by the
architecture scan. Agent-authored content renders as text, never as HTML.

**Reconnect rebuilds from the platform.** `RealtimeService` buffers and replays nothing. On
reconnect it raises `resyncRequired` and the surface re-reads the API (FR-SESS-019). A notification
says something changed; it never carries a decision.

**Accessibility is not a surface-by-surface choice.** WCAG 2.2 Level AA on all three, with no
best-effort surface (FR-SURF-010). A failure is never presented as an empty result (FR-SURF-016),
and suspended, pending and expired are conveyed by glyph and text as well as colour (FR-SURF-013).

## Conventions

Standalone components, strict TypeScript, `inject()` over constructor injection, kebab-case
filenames, `.spec.ts` tests colocated with what they test. No state-management framework is adopted;
the constitution forbids one until a requirement justifies it.
