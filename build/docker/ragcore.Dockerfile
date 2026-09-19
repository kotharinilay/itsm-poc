# syntax=docker/dockerfile:1
#
# The RagCore execution leg (constitution §Containers, research R-012).
#
# THE TWO IMAGES ARE HARDENED AGAINST DIFFERENT LISTS, and that is deliberate rather than an
# inconsistency to be tidied away (plan Stage 10). `chiseled` is a .NET image family and has no
# Python equivalent; R-012 chose a slim Debian base, which has a shell by design. A single combined
# list would be unsatisfiable, so each image is held to the list that is actually achievable for it
# — and every difference below is therefore a stated position rather than a gap.
#
# What this image is held to:
#   - digest-pinned in production
#   - non-root under a fixed, documented UID
#   - installed from uv.lock ONLY
#   - no build toolchain and no package-manager cache in the final layer
#   - read-only root filesystem, with every writable path named explicitly
#
# WHY MULTI-STAGE. The dependency install needs a resolver, a compiler for anything without a wheel,
# and a package cache. None of those belong in a running container: a compiler in the production
# image turns a file-write primitive into code execution, and a package cache is a writable
# directory nobody audits. They stay in the builder, and only the resolved virtual environment
# crosses.

# ---------------------------------------------------------------------------------------------
# Runtime base — DIGEST PIN
# ---------------------------------------------------------------------------------------------
# The tag is carried alongside for readability; the digest is what is resolved. Re-pinning is an
# ordinary reviewed pull request opened by .github/workflows/base-image-digests.yml monthly, on a
# High or Critical CVE, or on a base-image runtime patch. A digest never reaches production on a
# green scan alone — it passes the full suite as well (plan Stage 10).
#
# The digest below is a placeholder and MUST be replaced with a resolved value before this image is
# built for a deployed environment. It is deliberately not a working digest: a plausible-looking one
# invented here would be indistinguishable from a reviewed one, and the point of pinning is that
# somebody looked. Built as committed, the build therefore FAILS — which is the intent.
#
# It is an ARG so that CI can prove the image builds, starts and is hardened BEFORE a digest exists
# (build/scripts/smoke-images.sh passes the bare tag, labelled as a CI-only override). BuildKit
# parses every stage's FROM, so without the ARG not even `--target build` could run.
ARG RUNTIME_BASE=python:3.12-slim-bookworm@sha256:REPLACE_WITH_RESOLVED_DIGEST

# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------
# The builder is pinned by tag, not by digest, for the same reason as the .NET SDK stage: what it
# produces is reproducible from uv.lock and the source, so a newer patch builder producing the same
# environment is not a supply-chain risk in the way a newer runtime layer would be.
FROM python:3.12-slim-bookworm AS build

# uv from its own distroless image rather than `pip install uv`: it is the tool that enforces the
# lockfile, so bootstrapping it through an unlocked install would leave the one thing guaranteeing
# reproducibility as the one thing installed unreproducibly.
COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# /app, THE SAME PATH THE RUNTIME USES. A virtual environment is not relocatable: every console
# script (uvicorn, alembic) carries an absolute shebang naming the interpreter where the venv was
# CREATED. Built at /build and copied to /app, the entrypoint was `#!/build/.venv/bin/python` in an
# image with no /build — `exec uvicorn` failed and no replica or migration job could start.
WORKDIR /app

# The manifest and the lockfile first, so a source-only change does not re-resolve or re-download
# anything. This is the layer that takes the time.
COPY ragcore/pyproject.toml ragcore/uv.lock ./

# --frozen: THE LOCKFILE IS AUTHORITATIVE, and an out-of-date one fails the build rather than
# resolving to something nobody reviewed. --no-dev: the production image carries no test framework,
# no linter and no type checker — each is an import surface and none of them runs here.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY ragcore/src/ ./src/
COPY ragcore/workers/ ./workers/
COPY ragcore/migrations/ ./migrations/
COPY ragcore/scripts/ ./scripts/
COPY ragcore/alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------------
# The digest-pinned base declared at the top of this file.
FROM ${RUNTIME_BASE} AS runtime

# UID 10001, FIXED AND DOCUMENTED. A high, static, numeric UID rather than a name: Container Apps
# and every scanner compare numbers, and a name resolved against the image's own /etc/passwd tells
# you nothing about what the kernel sees. High enough not to collide with a distribution user, and
# identical across every rebuild so a mounted volume's ownership does not shift underneath a
# deployment.
#
# `--no-log-init` avoids useradd allocating a sparse lastlog file sized by the UID, which for a
# five-digit UID is gigabytes of image for a file nothing reads.
RUN groupadd --system --gid 10001 synthia \
    && useradd --system --no-log-init --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin synthia \
    # NO PACKAGE MANAGER IN THE PRODUCTION IMAGE (constitution §Containers). The slim base ships
    # pip, apt and dpkg; each is a way to install something at runtime, and none of them runs here.
    # Removed in the SAME layer that would otherwise keep them — deleting in a later layer removes
    # them from the filesystem and leaves them in the image.
    #
    # apt is purged through dpkg so the package database stays consistent, then the dpkg binaries
    # themselves are removed. /var/lib/dpkg/status is KEPT: it is what an image scanner reads to
    # inventory the OS packages, and an image nobody can scan is not a hardened one.
    && rm -rf /usr/local/bin/pip /usr/local/bin/pip3* /usr/local/lib/python3.12/site-packages/pip \
        /usr/local/lib/python3.12/site-packages/pip-*.dist-info /usr/local/lib/python3.12/ensurepip \
    && dpkg --purge --force-remove-essential --force-depends apt \
    && rm -rf /var/lib/apt /var/cache/apt /etc/apt \
    && rm -f /usr/bin/dpkg /usr/bin/dpkg-* /usr/sbin/dpkg-*

WORKDIR /app

# Only the resolved virtual environment and the source cross from the builder. No uv, no compiler,
# no package cache, no lockfile — nothing that could install anything at runtime. The paths are the
# same on both sides; see the note on the builder's WORKDIR for why that is load-bearing.
COPY --from=build --chown=10001:10001 /app/.venv /app/.venv
COPY --from=build --chown=10001:10001 /app/src /app/src
COPY --from=build --chown=10001:10001 /app/workers /app/workers

# The migration job runs from this same image (build/docker/migrate.job.yaml), as a different
# principal, so the revisions and the provisioning script must be present. They are inert in an
# application replica: that principal holds no DDL, so running them there would fail rather than
# apply anything.
COPY --from=build --chown=10001:10001 /app/migrations /app/migrations
COPY --from=build --chown=10001:10001 /app/scripts /app/scripts
COPY --from=build --chown=10001:10001 /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    # Bytecode is compiled in the builder (UV_COMPILE_BYTECODE). Writing it at runtime would need a
    # writable source tree, which is exactly what the read-only root filesystem forbids.
    PYTHONDONTWRITEBYTECODE=1 \
    # Unbuffered, so a log line reaches the collector when it is written rather than when the
    # process exits. A buffered crash loses the lines explaining the crash.
    PYTHONUNBUFFERED=1 \
    # Faulthandler on SIGSEGV and friends: a native crash inside a C extension otherwise leaves an
    # exit code and nothing else.
    PYTHONFAULTHANDLER=1

USER 10001

# READ-ONLY ROOT FILESYSTEM, with every writable path named in
# build/docker/containerapps/ragcore.yaml rather than implied here. /tmp is the only one, and it is
# an EmptyDir mount: nothing this process writes is expected to survive the replica.
#
# The application writes no files. Logs go to stdout as JSON, telemetry goes to the exporter, and
# every durable thing goes to PostgreSQL.

EXPOSE 8000

# No HEALTHCHECK instruction. Container Apps probes over HTTP against /health/live and
# /health/ready, declared in build/docker/containerapps/ragcore.yaml. A Docker-level healthcheck
# would duplicate them and would be the copy nobody updates.

# Uvicorn directly, with no shell form and no process manager.
#
# EXEC FORM IS LOAD-BEARING FOR THE DRAIN. In shell form the container's PID 1 is /bin/sh, which
# does not forward SIGTERM to its child — so Container Apps' termination signal would be swallowed,
# the application would never begin draining, and every shutdown would be a 25-second wait followed
# by a SIGKILL mid-request. In exec form uvicorn is PID 1 and receives the signal itself.
#
# --timeout-graceful-shutdown is one second under the platform's 25-second grace period, so uvicorn
# finishes first and exits cleanly rather than being killed while it is still tidying up.
#
# --no-server-header: the version banner tells an attacker which advisories to read and tells nobody
# else anything.
#
# --no-access-log: request visibility comes from OpenTelemetry spans, which carry the route, the
# status, the duration, the correlation identifier and the organisation. Uvicorn's access log
# carries the raw request line, which means query strings — an unstructured second log stream whose
# one distinguishing feature is that it is the one place a token in a URL would land.
ENTRYPOINT ["uvicorn", "ragcore.api.app:create_app", \
            "--factory", \
            "--host", "0.0.0.0", \
            "--port", "8000", \
            "--timeout-graceful-shutdown", "24", \
            "--no-server-header", \
            "--no-access-log"]
