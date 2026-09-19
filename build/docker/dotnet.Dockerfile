# syntax=docker/dockerfile:1
#
# The read-only .NET monolith (constitution §Containers, research R-011).
#
# WHY MULTI-STAGE IS MANDATORY, not merely tidy: SDK images are not produced for chiseled variants,
# so the only way to reach a chiseled runtime is to build somewhere else and copy the output in.
#
# WHAT CHISELED BUYS: no shell and no package manager in the production image. An attacker who
# achieves execution finds nothing to execute — no /bin/sh, no apt, no curl. It also ships a
# non-root user already configured, so running unprivileged is the default rather than a flag
# somebody has to remember.
#
# WHAT CHISELED COSTS: no ICU and no tzdata. That is affordable here only because the product is
# English-only (spec FR-SURF-014) and every timestamp is DateTimeOffset in UTC. IF PER-ORGANISATION
# TIMEZONE DISPLAY IS EVER REQUIRED, this must move to the -extra variant. It is not a free choice
# to revisit silently.

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
# An ARG so that CI can prove the image builds and starts before a digest exists
# (build/scripts/smoke-images.sh passes the bare tag as a CI-only override). BuildKit parses every
# stage's FROM, so without the ARG not even `--target build` could run.
ARG RUNTIME_BASE=mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled@sha256:REPLACE_WITH_RESOLVED_DIGEST

# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------
# The SDK stage is not the shipped image, so it is pinned by tag rather than by digest: what it
# produces is reproducible from the lockfile and the source, and a newer patch SDK building the
# same source is not a supply-chain risk in the way a newer runtime layer would be.
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /source

# Central package management means the version list is one file.
#
# THE API PROJECT, NOT THE SOLUTION. Restoring Synthia.sln needs every test project, and
# .dockerignore excludes dotnet/tests/ — the production image runs no tests and its context should
# not carry them. Restoring the solution therefore failed on a directory that was never sent, and
# no image could be built at all. The API project's reference graph is exactly what gets published.
COPY dotnet/Directory.Build.props dotnet/Directory.Packages.props dotnet/.editorconfig ./dotnet/
COPY dotnet/src/ ./dotnet/src/

WORKDIR /source/dotnet
RUN dotnet restore src/Synthia.Api/Synthia.Api.csproj

# -warnaserror here as well as in CI. An image is only allowed to exist if it would have passed the
# merge gate, so a local `docker build` cannot produce something CI would refuse.
RUN dotnet publish src/Synthia.Api/Synthia.Api.csproj \
    --configuration ${BUILD_CONFIGURATION} \
    --no-restore \
    -warnaserror \
    --output /app/publish

# ---------------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------------
# The digest-pinned base declared at the top of this file.
FROM ${RUNTIME_BASE} AS runtime

# 1654 is the chiseled convention, and the image already defines the user. Naming it explicitly
# means a base-image change that altered the default fails visibly rather than silently running as
# somebody else.
USER 1654

WORKDIR /app
COPY --from=build --chown=1654:1654 /app/publish .

# The non-root user cannot bind a privileged port, and would not be granted the capability if it
# could. 8080 matches ContainerApps:Port.
EXPOSE 8080
ENV ASPNETCORE_HTTP_PORTS=8080 \
    DOTNET_RUNNING_IN_CONTAINER=true \
    DOTNET_EnableDiagnostics=0

# No HEALTHCHECK instruction. Container Apps probes over HTTP against /health/live and
# /health/ready, and a Docker-level healthcheck would need a shell this image does not have.
# The probes are declared in build/docker/containerapps/monolith.yaml.

ENTRYPOINT ["./Synthia.Api"]
