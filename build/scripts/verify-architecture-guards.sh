#!/usr/bin/env bash
#
# Phase 2 checkpoint: "Every architecture test fails when its violation is planted and passes
# otherwise."
#
# This plants each violation class, asserts the guard rejects it, and removes it. It exists because
# one of these guards did NOT work when first written: ModuleIsolationTests reflected over compiled
# metadata, and the C# compiler omits a reference whose types are never used — so a module that
# declared a ProjectReference on another module but had not used it yet passed cleanly. That is the
# exact state a boundary breach passes through on its way in.
#
# A guard nobody has seen fail is a guard nobody knows works.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

failures=0
restore=()

cleanup() {
  for entry in "${restore[@]:-}"; do
    [ -z "$entry" ] && continue
    src="${entry%%:*}"
    dst="${entry##*:}"
    if [ "$src" = "RM" ]; then
      rm -rf "$dst"
    elif [ -f "$src" ]; then
      cp "$src" "$dst"
      rm -f "$src"
    fi
  done
}
trap cleanup EXIT

expect_fail() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '  \xe2\x9c\x97 NOT CAUGHT: %s\n' "$description"
    failures=$((failures + 1))
  else
    printf '  \xe2\x9c\x93 caught: %s\n' "$description"
  fi
}

py_arch() { (cd ragcore && uv run pytest tests/architecture -q); }
py_leak() { (cd ragcore && uv run pytest tests/egress/test_no_provider_leak.py -q); }
py_isolation() { (cd ragcore && uv run pytest tests/isolation -q -m 'not integration'); }
py_leakage() { (cd ragcore && uv run pytest tests/security/test_no_leakage.py -q); }
py_config()  { (cd ragcore && uv run pytest tests/unit/test_settings.py tests/unit/test_cache.py -q); }
py_edge()    { (cd ragcore && uv run pytest tests/security/test_edge_topology.py -q); }
net_routing() { (cd dotnet && dotnet test tests/Synthia.ArchitectureTests --nologo -v quiet --filter 'FullyQualifiedName~ApimRoutingTests'); }
net_arch() { (cd dotnet && dotnet test tests/Synthia.ArchitectureTests --nologo -v quiet); }
net_build() { (cd dotnet && dotnet build Synthia.sln --nologo -v quiet -warnaserror); }

echo "Verifying architecture guards reject each violation class..."

# --- 1: a provider package reaches the pure domain -------------------------
printf 'import pydantic\n' > ragcore/src/ragcore/domain/__planted.py
restore+=("RM:ragcore/src/ragcore/domain/__planted.py")
expect_fail "provider import in domain/" py_arch
rm -f ragcore/src/ragcore/domain/__planted.py

# --- 2: RagCore imports a .NET namespace -----------------------------------
printf 'from Synthia.Contracts import Thing\n' > ragcore/src/ragcore/__planted.py
restore+=("RM:ragcore/src/ragcore/__planted.py")
expect_fail "RagCore importing a .NET namespace" py_arch
rm -f ragcore/src/ragcore/__planted.py

# --- 3: authorization turned into an injectable port -----------------------
cp ragcore/src/ragcore/application/ports.py /tmp/synthia-ports.bak
restore+=("/tmp/synthia-ports.bak:ragcore/src/ragcore/application/ports.py")
cat >> ragcore/src/ragcore/application/ports.py <<'PLANTED'


@runtime_checkable
class AuthorizationPort(Protocol):
    """Planted by verify-architecture-guards.sh."""

    def check(self) -> bool:
        """Planted."""
        ...
PLANTED
expect_fail "authorization exposed as an injectable port" py_arch
cp /tmp/synthia-ports.bak ragcore/src/ragcore/application/ports.py
rm -f /tmp/synthia-ports.bak

# --- 4: a module declares a reference to another module --------------------
WORK=dotnet/src/Modules/Synthia.Modules.Work/Synthia.Modules.Work.csproj
cp "$WORK" /tmp/synthia-work.bak
restore+=("/tmp/synthia-work.bak:$WORK")
sed -i 's#</Project>#  <ItemGroup>\n    <ProjectReference Include="../Synthia.Modules.Audit/Synthia.Modules.Audit.csproj" />\n  </ItemGroup>\n\n</Project>#' "$WORK"
expect_fail "module declaring a reference to another module" net_arch
cp /tmp/synthia-work.bak "$WORK"
rm -f /tmp/synthia-work.bak

# --- 5: DateTime.Now in a production assembly ------------------------------
cat > dotnet/src/Synthia.SharedKernel/__Planted.cs <<'PLANTED'
namespace Synthia.SharedKernel;
internal static class Planted
{
    public static DateTime When() => DateTime.Now;
}
PLANTED
restore+=("RM:dotnet/src/Synthia.SharedKernel/__Planted.cs")
# Caught at BUILD by the analyzer set, before the test suite runs. Defence in depth: the build
# gate and BannedApiTests both cover it, and the build is the faster feedback.
expect_fail "DateTime.Now in a production assembly" net_build
rm -f dotnet/src/Synthia.SharedKernel/__Planted.cs

# --- 6: the dependency floor gains a dependency ----------------------------
SK=dotnet/src/Synthia.SharedKernel/Synthia.SharedKernel.csproj
cp "$SK" /tmp/synthia-sk.bak
restore+=("/tmp/synthia-sk.bak:$SK")
sed -i 's#</Project>#  <ItemGroup>\n    <ProjectReference Include="../Synthia.Contracts/Synthia.Contracts.csproj" />\n  </ItemGroup>\n\n</Project>#' "$SK"
# Fails as a circular dependency at restore: Contracts already depends on SharedKernel. The
# strongest form of enforcement available — it cannot even be compiled.
expect_fail "SharedKernel taking a platform dependency" net_build
cp /tmp/synthia-sk.bak "$SK"
rm -f /tmp/synthia-sk.bak

# --- 7: a model provider SDK reaches RagCore -------------------------------
# The single-egress rule (FR-OPS-007) rests on four independent facts; this plants a violation of
# the one that is code. The other three - no Foundry role assignment, ModelEgressPort being the
# only shape a call takes, and settings having no provider field - cannot be planted here because
# two of them are configuration and one is a type.
printf 'from openai import AzureOpenAI\n' > ragcore/src/ragcore/__planted_model.py
restore+=("RM:ragcore/src/ragcore/__planted_model.py")
expect_fail "a model provider SDK imported in RagCore" py_arch
rm -f ragcore/src/ragcore/__planted_model.py

# --- 8: a provider endpoint inside the model package -----------------------
# Deliberately planted INSIDE model/, which is where a direct call would be least
# conspicuous: the directory name is right, so only the guard notices. The gateway client needs no
# provider endpoint either - it posts to the gateway, and the gateway knows the providers.
printf 'ENDPOINT = "https://contoso.openai.azure.com"\n' \
  > ragcore/src/ragcore/model/__planted_endpoint.py
restore+=("RM:ragcore/src/ragcore/model/__planted_endpoint.py")
expect_fail "a provider endpoint inside model/" py_arch
rm -f ragcore/src/ragcore/model/__planted_endpoint.py

# --- 9: a provider's vocabulary reaches the application layer --------------
# The half that imports nothing and couples just as firmly: no import to spot, and the word
# outlives the adapter that justified it.
cat > ragcore/src/ragcore/application/__planted_vocabulary.py <<'PLANTED'
"""Planted by verify-architecture-guards.sh."""


def lookup(sys_id: str) -> str:
    """Planted."""
    return sys_id
PLANTED
restore+=("RM:ragcore/src/ragcore/application/__planted_vocabulary.py")
expect_fail "a provider's own vocabulary in application/" py_leak
rm -f ragcore/src/ragcore/application/__planted_vocabulary.py

# --- 10: an unfiltered retrieval path ---------------------------------------
# Isolation is absolute (Principle IV): a code path able to issue an unfiltered query MUST NOT
# exist. Planted as the shape it would actually take - a caller-supplied filter parameter, which
# passes every behavioural test in the suite until something passes None.
cp ragcore/src/ragcore/retrieval/search.py /tmp/synthia-search.bak
restore+=("/tmp/synthia-search.bak:ragcore/src/ragcore/retrieval/search.py")
sed -i 's#    async def search(self, tenant: TenantContext, query: str, limit: int)#    async def search(self, tenant: TenantContext, query: str, limit: int, filter: str = "")#' \
  ragcore/src/ragcore/retrieval/search.py
expect_fail "a caller-supplied filter on the retrieval boundary" py_isolation
cp /tmp/synthia-search.bak ragcore/src/ragcore/retrieval/search.py
rm -f /tmp/synthia-search.bak

# --- 11: a payload or header collection reaches a log sink ---------------------
# Logs leak no secret, token, authorization header or sensitive payload (plan Stage 10 security).
# The redacting filter is the backstop; this is the shape that defeats a backstop, because a dict
# of headers renders as text the filter has to recognise rather than being handed the value.
cat > ragcore/src/ragcore/__planted_leak.py <<'PLANTED'
"""Planted by verify-architecture-guards.sh."""

import logging

_log = logging.getLogger(__name__)


def report(headers: dict[str, str]) -> None:
    """Planted."""
    _log.info("inbound %s", headers)
PLANTED
restore+=("RM:ragcore/src/ragcore/__planted_leak.py")
expect_fail "a header collection passed to a log call" py_leakage
rm -f ragcore/src/ragcore/__planted_leak.py

# --- 12: a log message built with an f-string ----------------------------------
# Two defects in one: the message stops being aggregatable, and the value is spliced into free text
# where the redactor must find it by shape rather than being handed it as an argument.
cat > ragcore/src/ragcore/__planted_fstring.py <<'PLANTED'
"""Planted by verify-architecture-guards.sh."""

import logging

_log = logging.getLogger(__name__)


def report(value: str) -> None:
    """Planted."""
    _log.info(f"value is {value}")
PLANTED
restore+=("RM:ragcore/src/ragcore/__planted_fstring.py")
expect_fail "a log message built with an f-string" py_leakage
rm -f ragcore/src/ragcore/__planted_fstring.py

# --- 13: telemetry retention drifting from the workspace -----------------------
# Two places hold the same number (FR-OPS-011). The drift would be invisible, and the weaker of the
# two is the one that would matter: a workspace retaining for months makes it plausible to answer an
# audit question from a dashboard, which FR-OPS-004 prohibits.
SETTINGS=ragcore/src/ragcore/config/settings.py
cp "$SETTINGS" /tmp/synthia-settings.bak
restore+=("/tmp/synthia-settings.bak:$SETTINGS")
sed -i 's/    retention_days: int = Field(default=30, ge=1, le=90)/    retention_days: int = Field(default=180, ge=1, le=365)/' "$SETTINGS"
expect_fail "telemetry retention drifting from the workspace policy" py_config
cp /tmp/synthia-settings.bak "$SETTINGS"
rm -f /tmp/synthia-settings.bak

# --- 14: a cache entry that can be written without an expiry -------------------
# Redis is transient only (Principle IV). An entry with no TTL is a durable record, and this is the
# single edit that turns the cache into one - a default on a parameter nobody would think to pass.
CACHE=ragcore/src/ragcore/infrastructure/cache.py
cp "$CACHE" /tmp/synthia-cache.bak
restore+=("/tmp/synthia-cache.bak:$CACHE")
sed -i 's/    async def put(self, tenant: TenantContext, key: str, value: str, \*, ttl_seconds: int) -> None:/    async def put(self, tenant: TenantContext, key: str, value: str, ttl_seconds: int = 0) -> None:/' "$CACHE"
expect_fail "a cache write with an optional TTL" py_config
cp /tmp/synthia-cache.bak "$CACHE"
rm -f /tmp/synthia-cache.bak

# --- 15: a read view routed to the deployable that writes ----------------------
# The routing rule that is invisible when it is wrong. A /views path delivered to RagCore reaches a
# service that serves the audience but not the route, and returns a 404 indistinguishable from a
# client calling something that does not exist. Both stacks read the same registry, so both are
# asked - the .NET side owns the read-only claim (ADR-0001).
APIS=build/infra/apim/apis.json
cp "$APIS" /tmp/synthia-apis.bak
restore+=("/tmp/synthia-apis.bak:$APIS")
sed -i '0,/"backend": "monolith"/s//"backend": "ragcore"/' "$APIS"
expect_fail "a read view routed to the write deployable" py_edge
cp /tmp/synthia-apis.bak "$APIS"

# --- 16: a hand-written OpenAPI document imported into the gateway -------------
# Every document is emitted from a RUNNING service (FR-DEMO-013). A hand-maintained copy imported
# here drifts from what the service accepts, and the drift is invisible until a client believes it.
sed -i '0,/"handWritten": false/s//"handWritten": true/' "$APIS"
expect_fail "a hand-written OpenAPI document imported" py_edge
cp /tmp/synthia-apis.bak "$APIS"

# --- 17: a backend shared secret -----------------------------------------------
# APIM presents NO credential on this hop: the client certificate that used to serve that purpose
# is deferred (docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md) and nothing
# replaced it. This case matters MORE after that deferral, not less - an unguarded hop is exactly
# where somebody reaches for a key, and a standing credential is what the ADR refused to adopt as
# an interim substitute.
#
# Planted by ADDING a credentials block, since there is no longer one to rewrite.
sed -i 's|"containerApp": "build/docker/containerapps/ragcore.yaml",|"containerApp": "build/docker/containerapps/ragcore.yaml", "credentials": { "type": "header", "apiKey": "{{ragcore-backend-key}}" },|' "$APIS"
expect_fail "a shared secret on an APIM backend" py_edge
cp /tmp/synthia-apis.bak "$APIS"

# --- 18: a per-organisation budget re-keyed to something a caller controls ------
# FR-OPS-005 is per ORGANISATION. Counting by IP throttles the wrong callers - one organisation
# behind one NAT is one IP - and a key a caller can set is a budget a caller escapes.
CUSTOMER=build/infra/apim/customer.v1.xml
cp "$CUSTOMER" /tmp/synthia-customer.bak
restore+=("/tmp/synthia-customer.bak:$CUSTOMER")
sed -i 's|counter-key="@(context.Request.Headers.GetValueOrDefault("X-Idp-Tenant-Id", string.Empty))"|counter-key="@(context.Request.IpAddress)"|' "$CUSTOMER"
expect_fail "a per-organisation budget re-keyed to the client IP" py_edge
cp /tmp/synthia-customer.bak "$CUSTOMER"
rm -f /tmp/synthia-customer.bak

# --- 19: the WAF switched out of prevention mode -------------------------------
# Detection mode is a WAF that writes reports about the attack it allowed through.
FD=build/infra/frontdoor/front-door.json
cp "$FD" /tmp/synthia-fd.bak
restore+=("/tmp/synthia-fd.bak:$FD")
sed -i 's/"mode": "Prevention"/"mode": "Detection"/' "$FD"
expect_fail "the public edge WAF switched to Detection mode" py_edge
cp /tmp/synthia-fd.bak "$FD"
rm -f /tmp/synthia-fd.bak

# --- 20: a write route pointed at the read-only deployable ---------------------
# The .NET half of the same registry. Its identity holds no write role, so this would fail at the
# platform - but only AFTER being routed there, as a 500 nobody can place.
python - <<'PLANTED'
import json, pathlib
p = pathlib.Path("build/infra/apim/apis.json")
d = json.loads(p.read_text(encoding="utf-8"))
d["apis"].append({
    "id": "planted-write-on-monolith", "displayName": "planted", "audience": "staff",
    "path": "api/staff/v1/approvals", "protocols": ["https"], "backend": "monolith",
    "policy": "build/infra/apim/staff.v1.xml",
    "openApi": {"source": "build/contracts/dotnet/staff.v1.openapi.json",
                "generatedBy": "planted", "handWritten": False},
    "subscriptionRequired": False})
p.write_text(json.dumps(d, indent=2), encoding="utf-8")
PLANTED
expect_fail "a write route on the read-only deployable" net_routing
cp /tmp/synthia-apis.bak "$APIS"
rm -f /tmp/synthia-apis.bak

# --- clean tree must pass --------------------------------------------------
(cd dotnet && dotnet build Synthia.sln --nologo -v quiet >/dev/null 2>&1)
if py_arch >/dev/null 2>&1 && py_leak >/dev/null 2>&1 && py_isolation >/dev/null 2>&1 \
  && net_arch >/dev/null 2>&1; then
  printf '  \xe2\x9c\x93 clean tree accepted\n'
else
  printf '  \xe2\x9c\x97 clean tree REJECTED - a guard has a false positive\n'
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  printf '\nGuard verification FAILED: %d case(s) wrong.\n' "$failures"
  exit 1
fi

printf '\nArchitecture guards verified: every violation class is rejected, a clean tree passes.\n'
exit 0
