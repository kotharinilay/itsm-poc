# syntax=docker/dockerfile:1
#
# The Synthia Integrations Service (constitution §Containers, ADR-0007, specification §21.6).
#
# THIS IMAGE IS HELD TO THE SAME LIST AS RAGCORE'S, and for the same reasons — digest-pinned in
# production, non-root under a fixed documented UID, installed from uv.lock only, no build toolchain
# or package cache in the final layer, read-only root filesystem with every writable path named.
# See build/docker/ragcore.Dockerfile for why the Python and .NET images are hardened against
# different lists; nothing here changes that reasoning.
#
# WHAT IS DIFFERENT, AND WHY IT MATTERS MORE HERE. This is the only container in the platform that
# holds per-organisation connector credentials and the only one with an egress path to customer
# systems. Every hardening measure below is therefore load-bearing twice over: a file-write
# primitive in this image reaches a vault client, not a read model.
#
# NO MIGRATIONS CROSS. Unlike RagCore's image, this one carries no Alembic revisions and no
# alembic.ini: one Alembic project owns both schemas (ADR-0003 as extended by ADR-0007), and it runs
# from RagCore's image as the migration principal. Shipping a second copy of the revisions here
# would create a second way to apply them, which is the thing a single gated job exists to prevent.

# ---------------------------------------------------------------------------------------------
# Runtime base — DIGEST PIN
# ---------------------------------------------------------------------------------------------
# The tag is carried for readability; the digest is what resolves. Re-pinning is an ordinary
# reviewed pull request opened by .github/workflows/base-image-digests.yml, and a digest never
# reaches production on a green scan alone — it passes the full suite as well.
#
# The digest below is a PLACEHOLDER and MUST be replaced with a resolved value before this image is
# built for a deployed environment. It is deliberately not a working digest: a plausible-looking one
# invented here would be indistinguishable from a reviewed one, and the point of pinning is that
# somebody looked. Built as committed, the build therefore FAILS — which is the intent.
#
# An ARG so that CI can prove the image builds, starts and is hardened before a digest exists
# (build/scripts/smoke-images.sh passes the bare tag as a CI-only override). BuildKit parses every
# stage's FROM, so without the ARG not even `--target build` could run.
ARG RUNTIME_BASE=python:3.12-slim-bookworm@sha256:REPLACE_WITH_RESOLVED_DIGEST

# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------
# Pinned by tag rather than digest, as in the RagCore builder: what it produces is reproducible from
# uv.lock and the source, so a newer patch builder producing the same environment is not the
# supply-chain risk a newer runtime layer would be.
FROM python:3.12-slim-bookworm AS build

# uv from its own distroless image rather than `pip install uv`: it is the tool that enforces the
# lockfile, so bootstrapping it through an unlocked install would leave the one thing guaranteeing
# reproducibility as the one thing installed unreproducibly.
COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# /app, THE SAME PATH THE RUNTIME USES. A virtual environment is not relocatable: every console
# script carries an absolute shebang naming the interpreter where the venv was CREATED. Built at
# /build and copied to /app, the entrypoint was `#!/build/.venv/bin/python` in an image with no
# /build, and `exec uvicorn` failed on every start.
WORKDIR /app

# Manifest and lockfile first, so a source-only change re-resolves nothing.
COPY integrations/pyproject.toml integrations/uv.lock ./

# --frozen: THE LOCKFILE IS AUTHORITATIVE, and an out-of-date one fails the build rather than
# resolving to something nobody reviewed. --no-dev: no test framework, no linter, no type checker in
# the production image — each is an import surface and none of them runs here.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY integrations/src/ ./src/
COPY integrations/workers/ ./workers/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------------
# The digest-pinned base declared at the top of this file.
FROM ${RUNTIME_BASE} AS runtime

# UID 10002, FIXED AND DOCUMENTED. Deliberately NOT 10001: RagCore uses that, and two services
# sharing a UID would be indistinguishable to anything that authorizes by numeric identity — a
# volume ACL, a filesystem audit, a runtime policy. They are separate principals, so they get
# separate numbers.
RUN groupadd --system --gid 10002 synthia \
    && useradd --system --no-log-init --uid 10002 --gid 10002 --home-dir /app --shell /usr/sbin/nologin synthia \
    # NO PACKAGE MANAGER IN THE PRODUCTION IMAGE (T269, constitution §Containers). The slim base
    # ships pip, apt and dpkg; in the one container holding connector credentials, each is a way to
    # install tooling next to a vault client. Removed in the SAME layer that would otherwise keep
    # them — deleting in a later layer leaves them in the image.
    #
    # apt is purged through dpkg so the package database stays consistent, then the dpkg binaries
    # are removed. /var/lib/dpkg/status is KEPT: it is what an image scanner reads to inventory the
    # OS packages, and an image nobody can scan is not a hardened one.
    && rm -rf /usr/local/bin/pip /usr/local/bin/pip3* /usr/local/lib/python3.12/site-packages/pip         /usr/local/lib/python3.12/site-packages/pip-*.dist-info /usr/local/lib/python3.12/ensurepip     && dpkg --purge --force-remove-essential --force-depends apt     && rm -rf /var/lib/apt /var/cache/apt /etc/apt     && rm -f /usr/bin/dpkg /usr/bin/dpkg-* /usr/sbin/dpkg-*

WORKDIR /app

# Only the resolved virtual environment and the source cross. No uv, no compiler, no package cache,
# no lockfile — nothing that could install anything at runtime. Same paths on both sides; see the
# note on the builder's WORKDIR.
COPY --from=build --chown=10002:10002 /app/.venv /app/.venv
COPY --from=build --chown=10002:10002 /app/src /app/src
COPY --from=build --chown=10002:10002 /app/workers /app/workers

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    # Bytecode is compiled in the builder. Writing it at runtime would need a writable source tree,
    # which the read-only root filesystem forbids.
    PYTHONDONTWRITEBYTECODE=1 \
    # Unbuffered, so a log line reaches the collector when written rather than when the process
    # exits. A buffered crash loses the lines explaining the crash.
    PYTHONUNBUFFERED=1 \
    # Faulthandler on SIGSEGV and friends: a native crash inside a C extension otherwise leaves an
    # exit code and nothing else.
    PYTHONFAULTHANDLER=1

USER 10002

EXPOSE 8000

# The probe path is process-only and consults no dependency — a liveness probe that checked a
# dependency would restart a healthy process because something else was down, turning one outage
# into two. Readiness is configured on the Container App (build/docker/containerapps/), not here,
# because it is a scheduling concern rather than an image concern.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status==200 else 1)"]

# Exec form, no shell. A shell-form entrypoint makes PID 1 a shell that does not forward SIGTERM,
# so the 25-second drain the constitution requires would never reach the application and every
# scale-in would be a hard kill.
ENTRYPOINT ["uvicorn", "integrations.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
