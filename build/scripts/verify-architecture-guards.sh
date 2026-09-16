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
py_leak() { (cd ragcore && uv run pytest tests/integrations/test_no_provider_leak.py -q); }
py_isolation() { (cd ragcore && uv run pytest tests/isolation -q -m 'not integration'); }
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
# Deliberately planted INSIDE integrations/model/, which is where a direct call would be least
# conspicuous: the directory name is right, so only the guard notices. The gateway client needs no
# provider endpoint either - it posts to the gateway, and the gateway knows the providers.
printf 'ENDPOINT = "https://contoso.openai.azure.com"\n' \
  > ragcore/src/ragcore/integrations/model/__planted_endpoint.py
restore+=("RM:ragcore/src/ragcore/integrations/model/__planted_endpoint.py")
expect_fail "a provider endpoint inside integrations/model/" py_arch
rm -f ragcore/src/ragcore/integrations/model/__planted_endpoint.py

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
