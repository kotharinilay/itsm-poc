# 0009. Portal delivery: one public origin per browser surface

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** Platform architecture owner
- **Supersedes:** nothing
- **Amends:** nothing. It narrows a guard rule introduced alongside [0001](./0001-ragcore-owns-orchestration-dotnet-owns-read.md) and recorded in `build/scripts/check-edge-path.sh` — "Front Door publishes exactly one origin" — which was written when the edge carried APIs and nothing else
- **Related:** [0006](./0006-desktop-renderer-origin-and-csp-nonce.md) (the same policy, delivered by the Electron main process for the desktop renderer)

## Context and Problem Statement

`specs/001-platform-scaffold/plan.md` Stage 3 fixes a Content-Security-Policy baseline for the two
browser surfaces and requires it to be delivered **as a response header**, never a `<meta>` tag, so
injected markup cannot strip it and `frame-ancestors` is honoured at all. T048 built the policy
(`platform-core/security/content-security-policy.ts`) and unit-tested it.

**Nothing ever sent it.** `index.html` deferred the header to "the hosting tier"; no hosting tier
existed in `build/infra/` or `build/docker/`, and none was named anywhere. The portals were
buildable artifacts with no defined way to reach a browser. That gap was recorded as T344.

Two constraints shape the answer, and they pull against each other:

1. **The baseline needs a per-response nonce.** `style-src` carries `'nonce-{random}'`, matched by
   the `ngCspNonce` attribute Angular reads from the document. A static header cannot produce one —
   a fixed nonce is not a nonce — so *something must mint it per request and stamp both copies*.
   That rules out a storage account, a CDN header rule and an edge rewrite.
2. **Front Door is the sole public ingress** (specification §9.3), and the committed edge guard
   asserted it fronts exactly one origin: APIM. Any delivery of the portals adds public surface,
   which is exactly what that rule exists to notice.

## Decision

**Each browser surface is served by its own container app, behind its own Front Door endpoint and
its own origin group, over Private Link, under one shared WAF policy.**

| | |
|---|---|
| Customer portal | `synthia-customer-portal` endpoint → `customer-portal` origin group → `synthia-customer-portal` container app |
| Staff portal | `synthia-staff-portal` endpoint → `staff-portal` origin group → `synthia-staff-portal` container app |
| APIs | unchanged: `synthia-api` endpoint → `apim` origin group → APIM |

The container is a static file server (`build/docker/portals.Dockerfile`) that sets the CSP with a
fresh nonce per document response. It is the same `csp-host.mjs` the CSP tests drive, and it imports
`buildCspHeader` rather than restating the directive list — the policy that is tested is the policy
that is served.

**`check-edge-path.sh` rule 5 becomes an allow-list by name** — the gateway and the two portals,
each over Private Link — plus a new rule: **only the gateway origin may serve an `/api` path.**

### Why one origin per surface, rather than one host serving both

The browser's security boundary is the origin. Two portals on one host share `localStorage`,
`sessionStorage`, cookies, service-worker scope and script context — so a defect on the customer
surface, which is reachable by every end user of every organisation, would sit in the same origin as
a staff session that can act on other people's work. Separate host names cost two edge entries and
buy an isolation the browser already knows how to enforce and no application code has to remember.

### The bundle's environment comes from the tier, not the build

`platform.config.ts` carried a `gatewayOrigin`, an Entra authority and a client id, compiled into
the bundle with a comment saying a hosting tier would supply them. No tier did, so a deployed portal
would have shipped the **development default** — `https://localhost:7443`.

Images are promoted between environments **by digest** (specification §9.3). A value compiled in
would make the build per-environment, and the artefact reviewed in one environment would not be the
one running in the next. So the tier writes the values into the document it serves, as an inert
`<script type="application/json">` data block, and `readHostedConfig` reads them back at bootstrap:

- **A data block, not executable script**, so it needs no CSP nonce and executes nothing. The worst
  a bad value does is fail the assertions, loudly, at bootstrap.
- **Held to the same rules as a compiled configuration.** A supplied value goes through the secret
  scan and the HTTPS check — an origin that arrived over the wire deserves them more, not less. A
  key that looks like a secret is refused rather than dropped, because dropping it says nothing to
  whoever shipped it.
- **The compiled values remain as the fallback**, which is what a developer running `ng serve` gets.

### Why not through APIM

APIM is the API trust boundary: every API entry names an audience, an identity policy and a
generated OpenAPI document. A static bundle has none of those, and adding an entry that skipped all
three would weaken the invariant that makes the routing table reviewable — for traffic that needs
nothing APIM does.

## Consequences

**What this changes.** The platform now has three public host names instead of one. The edge guard,
both stacks' edge suites, and the image smoke gate were updated together; the guard's violation
classes grew a portal-route-publishing-`/api` case and a portal-origin-without-Private-Link case,
each proven by planting it.

**What this does not change, and each is asserted rather than assumed:**

- **No container app has external ingress.** The portal apps are internal-only, reached over Private
  Link, exactly like APIM. There is still no public route to any backend.
- **One WAF policy covers every endpoint.** Not one per endpoint: two policies drift, and the portal
  hosts would be the pair nobody upgraded.
- **No application data is served from a portal origin.** These containers hold no secret, no
  database connection and no managed identity beyond a registry pull. Everything the surface
  displays it fetches from the API host, through APIM, where identity is derived as for any other
  client.
- **The gateway remains the only origin serving `/api`.** A portal host answering an API path would
  reach the platform on a host APIM never saw; that is the bypass the single gateway exists to
  prevent, and it is now its own check.

**What it costs.** Two more container apps to deploy, scale and patch, for what is otherwise static
content — the price of a policy that cannot be expressed statically. The images are digest-pinned,
non-root, read-only and carry no package manager, like every other image here.

**The residual.** The portal origin is public surface, and a defect in the file server is a defect in
front of every user. It is deliberately tiny: it reads files under one directory, refuses anything
that escapes it, holds no state and speaks to nothing.

## Unresolved

- **Host names, DNS and the portal registrations** are provisioning concerns (specification §9.3).
  The placeholders in the Container App definitions — the portal host names, `${API_ORIGIN}`,
  `${ENTRA_AUTHORITY}`, the per-portal client ids — are bound by the deployment, and the portals
  must land on names the CSP's `connect-src` and APIM's CORS configuration agree about. That
  reconciliation lands with the first deployed environment (T227a).
- **Two Entra application registrations**, one per portal, follow from two origins: a browser
  redirect URI is origin-specific. Provisioning, not repository configuration.
- **The desktop renderer is unaffected.** It is served by the Electron main process over
  `app://renderer` with the same baseline (ADR-0006), and gets no host here.
