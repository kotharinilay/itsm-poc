# syntax=docker/dockerfile:1
#
# A browser portal, delivered (ADR-0009). One image per surface, selected by `--build-arg PORTAL`.
#
# WHAT THIS IMAGE IS FOR, and it is narrower than it looks: it serves a directory of static files
# and sets the Stage 3 Content-Security-Policy on every document. It holds no data, reaches no
# database and calls no service. Everything the surface displays it fetches from the API host,
# through Front Door and APIM, where identity is derived as for any other client.
#
# WHY A SERVER AT ALL, rather than a storage account or a static edge header. The CSP baseline
# carries a PER-RESPONSE nonce, matched by the `ngCspNonce` attribute in the document Angular
# reads. A static header cannot produce one - a fixed nonce is not a nonce - so something has to
# mint it per request and stamp both copies. That is the whole job of `csp-host.mjs`, and it is the
# same file the CSP tests drive (`apps/web/e2e/csp-hosting.spec.ts`): the policy that is tested is
# the policy that is served.
#
# ONE IMAGE PER PORTAL, NOT ONE SERVING BOTH. The browser's security boundary is the origin, so the
# customer and staff surfaces get separate hosts - and an image that could serve either is one
# deployment mistake away from serving both on one origin, which is the isolation ADR-0009 exists
# to keep.

# ---------------------------------------------------------------------------------------------
# Runtime base — DIGEST PIN
# ---------------------------------------------------------------------------------------------
# As with every other image here: the digest is a placeholder until somebody resolves and reviews
# one, so a build from the committed file FAILS. `build/scripts/smoke-images.sh` passes the bare tag
# as a labelled CI-only override, which is how the image is known to build and start before a digest
# exists. `.github/workflows/base-image-digests.yml` re-pins it.
ARG RUNTIME_BASE=node:22-bookworm-slim@sha256:REPLACE_WITH_RESOLVED_DIGEST

# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------
# Pinned by tag rather than digest, like the other builders: what it produces is reproducible from
# the lockfile and the source.
FROM node:22-bookworm-slim AS build

ARG PORTAL=customer-portal
WORKDIR /build

# The manifest and the lockfile first, so a source-only change does not re-resolve every package.
COPY apps/web/package.json apps/web/package-lock.json ./

# `npm ci` and never `npm install`: ci fails when the lockfile and the manifest disagree, which is
# the point of committing a lockfile at all.
RUN npm ci --no-audit --no-fund

COPY apps/web/ ./

# Libraries first — the workspace resolves them from dist/ — then the one portal this image serves.
# `--configuration production` is the default for `ng build` here, and it is what makes the CSP
# achievable: the AOT build emits no inline script and needs no 'unsafe-eval'.
RUN npm run build:libs && npx ng build "${PORTAL}"

# ---------------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------------
FROM ${RUNTIME_BASE} AS runtime

ARG PORTAL=customer-portal

# UID 10004, fixed and documented. Distinct from RagCore (10001), the Integrations Service (10002)
# and the monolith (1654): two components sharing a UID are indistinguishable to anything that
# authorizes by numeric identity.
RUN groupadd --system --gid 10004 synthia \
    && useradd --system --no-log-init --uid 10004 --gid 10004 --home-dir /app --shell /usr/sbin/nologin synthia \
    # NO PACKAGE MANAGER IN THE PRODUCTION IMAGE (constitution §Containers). The node image ships
    # npm and corepack; this image installs nothing at runtime and has no use for either. Removed
    # in the same layer that would otherwise keep them. /var/lib/dpkg/status is KEPT, because it is
    # what an image scanner reads to inventory the OS packages.
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
        /usr/local/bin/corepack /usr/local/lib/node_modules/corepack \
    && dpkg --purge --force-remove-essential --force-depends apt \
    && rm -rf /var/lib/apt /var/cache/apt /etc/apt \
    && rm -f /usr/bin/dpkg /usr/bin/dpkg-* /usr/sbin/dpkg-*

WORKDIR /app

# The built bundle, the server, and the policy the server imports. Nothing else crosses: no
# node_modules, no source, no lockfile — the server has no dependencies beyond Node itself.
COPY --from=build --chown=10004:10004 /build/dist/${PORTAL}/browser /app/dist/${PORTAL}/browser
COPY --from=build --chown=10004:10004 /build/scripts/csp-host.mjs /app/scripts/csp-host.mjs

# THE POLICY SOURCE, IMPORTED RATHER THAN RESTATED. `csp-host.mjs` imports `buildCspHeader` from
# this file, so the header served here is the one `platform-core` defines and its unit tests cover.
# A copy of the directive list in the server would be a second policy, and the second one is always
# the one nobody updates. Node strips the types at load (22.18+).
COPY --from=build --chown=10004:10004 \
    /build/projects/platform-core/src/lib/security/content-security-policy.ts \
    /app/projects/platform-core/src/lib/security/content-security-policy.ts

ENV NODE_ENV=production \
    SYNTHIA_PORTAL=${PORTAL} \
    PORT=8080 \
    # The container listens on every interface; the Container App's ingress is internal-only and
    # Front Door reaches it over Private Link, so "every interface" is one private network.
    SYNTHIA_BIND=0.0.0.0

USER 10004

# READ-ONLY ROOT FILESYSTEM. The server writes nothing: it reads files and streams them. The only
# writable path is /tmp, declared in the Container App definition.

EXPOSE 8080

# No HEALTHCHECK instruction: Container Apps probes /health/live over HTTP, declared in
# build/docker/containerapps/{customer,staff}-portal.yaml, and Front Door probes the same path as
# its origin health probe. A Docker-level check would be the third copy and the first to go stale.
#
# Exec form, so Node is PID 1 and receives SIGTERM itself rather than through a shell that would
# swallow it and turn every scale-in into a hard kill.
ENTRYPOINT ["node", "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", "scripts/csp-host.mjs"]
