#!/usr/bin/env bash
#
# Build every deployable image, start it exactly as committed, and prove it is hardened.
#
# WHY THIS EXISTS. Until it did, no pipeline ever built a runtime image. Three defects shipped
# behind that gap, each invisible to every test in the repository:
#
#   - the .NET image restored a solution whose test projects .dockerignore excludes, so it could
#     not be built at all;
#   - both Python images built their virtual environment at /build and ran it from /app, so the
#     entrypoint's shebang named an interpreter that did not exist and no container could start;
#   - the RagCore manifests configured a setting name the process did not read.
#
# WHAT IT ASSERTS, per image:
#   1. Built AS COMMITTED, the build is refused — the runtime digest is a placeholder until a person
#      resolves and reviews one, and that refusal is the control.
#   2. Built with the bare tag (a CI-ONLY override, never a production image), it builds.
#   3. It starts from its committed ENTRYPOINT, with a read-only root filesystem, and answers
#      /health/live. Configuration uses the SAME variable names the Container Apps manifests use, and
#      an unreachable database: liveness is process-only and must not depend on it.
#   4. It runs as a non-root numeric user.
#   5. Python images carry no package manager, and RagCore's migration tooling actually executes —
#      the migration job runs `alembic` from this image.
#
# Requires Docker. There is deliberately no "skip when Docker is missing": a gate that passes by not
# running is how the defects above went unnoticed.

set -uo pipefail
export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BASE="python:3.12-slim-bookworm"
DOTNET_BASE="mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled"
NODE_BASE="node:22-bookworm-slim"
UNREACHABLE_PG="unreachable.invalid"

failures=0
containers=()

ok()  { printf '  \xe2\x9c\x93 %s\n' "$1"; }
bad() { printf '  \xe2\x9c\x97 %s\n' "$1"; failures=$((failures + 1)); }

cleanup() {
  for name in "${containers[@]:-}"; do
    [ -n "$name" ] && docker rm -f "$name" >/dev/null 2>&1
  done
}
trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not available. This gate needs it and does not skip." >&2
  exit 1
fi

# $1 image name, $2 dockerfile, $3 runtime base tag, $4.. extra build arguments
build_image() {
  local image="$1" dockerfile="$2" base="$3"
  shift 3
  local extra=("$@")

  if docker build -q -f "$dockerfile" "${extra[@]}" -t "synthia-$image:placeholder" . >/dev/null 2>&1; then
    bad "$image: built with the placeholder digest — the pin no longer refuses an unreviewed base"
  else
    ok "$image: refused as committed (placeholder digest)"
  fi

  if docker build -q -f "$dockerfile" "${extra[@]}" --build-arg "RUNTIME_BASE=$base" -t "synthia-$image:smoke" . >/dev/null; then
    ok "$image: builds with the CI-only tag override"
    return 0
  fi
  bad "$image: does not build"
  return 1
}

# $1 image name, $2 container port, remaining: docker run environment arguments
start_and_probe() {
  local image="$1" port="$2"
  shift 2
  local name="synthia-smoke-$image-$$"
  containers+=("$name")

  if ! docker run -d --name "$name" --read-only --tmpfs /tmp -p "127.0.0.1::$port" "$@" \
      "synthia-$image:smoke" >/dev/null; then
    bad "$image: container did not start"
    return
  fi

  local host_port status=""
  host_port="$(docker port "$name" "$port/tcp" | head -1 | sed 's/.*://')"
  for _ in $(seq 1 30); do
    status="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$host_port/health/live" || true)"
    [ "$status" = "200" ] && break
    if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" != "true" ]; then
      break
    fi
    sleep 1
  done

  if [ "$status" = "200" ]; then
    ok "$image: starts from its committed entrypoint, read-only, and answers /health/live"
  else
    bad "$image: /health/live never answered 200 (last: '${status:-none}'). Container log:"
    docker logs "$name" 2>&1 | tail -15 | sed 's/^/      /'
  fi

  local user
  user="$(docker inspect -f '{{.Config.User}}' "synthia-$image:smoke")"
  if [ -n "$user" ] && [ "$user" != "0" ] && [ "$user" != "root" ]; then
    ok "$image: runs as non-root user $user"
  else
    bad "$image: runs as root (User='$user')"
  fi
}

# $1 image name
no_package_manager() {
  local image="$1"
  if docker run --rm --entrypoint python "synthia-$image:smoke" -c \
      "import importlib.util, shutil, sys
found = [t for t in ('pip', 'pip3', 'apt', 'apt-get', 'dpkg') if shutil.which(t)]
if importlib.util.find_spec('pip'): found.append('pip module')
print(found); sys.exit(1 if found else 0)" >/dev/null 2>&1; then
    ok "$image: no package manager in the runtime image"
  else
    bad "$image: a package manager is present in the runtime image"
  fi
}

echo "==> RagCore"
if build_image ragcore build/docker/ragcore.Dockerfile "$PYTHON_BASE"; then
  start_and_probe ragcore 8000 \
    -e "SYNTHIA_DB_DSN=postgresql+asyncpg://smoke@$UNREACHABLE_PG:5432/smoke"
  no_package_manager ragcore
  if docker run --rm --entrypoint alembic "synthia-ragcore:smoke" --help >/dev/null 2>&1; then
    ok "ragcore: the migration job's alembic executes"
  else
    bad "ragcore: alembic does not execute — the migration job cannot run"
  fi
fi

echo "==> Integrations"
if build_image integrations build/docker/integrations.Dockerfile "$PYTHON_BASE"; then
  start_and_probe integrations 8000 \
    -e "SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN=postgresql+asyncpg://smoke@$UNREACHABLE_PG:5432/smoke"
  no_package_manager integrations
fi

echo "==> Monolith"
if build_image monolith build/docker/dotnet.Dockerfile "$DOTNET_BASE"; then
  start_and_probe monolith 8080 \
    -e "ReadDatabase__ConnectionString=Host=$UNREACHABLE_PG;Port=5432;Database=smoke;Username=smoke"
fi

# The browser surfaces (ADR-0009). One image per portal, and the check that matters beyond starting
# is that the document carries the CSP: the image exists to send a policy no static host can.
for portal in customer-portal staff-portal; do
  echo "==> ${portal}"
  if build_image "$portal" build/docker/portals.Dockerfile "$NODE_BASE" --build-arg "PORTAL=$portal"; then
    start_and_probe "$portal" 8080

    policy="$(curl -s -D - -o /dev/null "http://127.0.0.1:$(docker port "synthia-smoke-$portal-$$" 8080/tcp | head -1 | sed 's/.*://')/" 2>/dev/null \
      | tr -d '\r' | grep -i '^content-security-policy:' || true)"
    if printf '%s' "$policy" | grep -q "nonce-"; then
      ok "$portal: serves the CSP baseline with a per-response nonce"
    else
      bad "$portal: the document carries no CSP nonce — the policy is not being sent"
    fi

    if printf '%s' "$policy" | grep -qE "unsafe-inline|unsafe-eval"; then
      bad "$portal: the served policy contains a weakening token"
    else
      ok "$portal: the served policy carries no weakening token"
    fi

    # The node image ships npm and corepack; this one installs nothing at runtime.
    if docker run --rm --entrypoint node "synthia-$portal:smoke" -e \
        "const {existsSync}=require('node:fs');
         const found=['/usr/local/bin/npm','/usr/local/bin/npx','/usr/local/bin/corepack','/usr/bin/apt-get','/usr/bin/dpkg'].filter(existsSync);
         console.log(found.join(' ')); process.exit(found.length ? 1 : 0);" >/dev/null 2>&1; then
      ok "$portal: no package manager in the runtime image"
    else
      bad "$portal: a package manager is present in the runtime image"
    fi
  fi
done

echo
if [ "$failures" -gt 0 ]; then
  echo "FAILED — $failures image check(s)."
  exit 1
fi
echo "Every image builds, starts as committed, and is hardened."
