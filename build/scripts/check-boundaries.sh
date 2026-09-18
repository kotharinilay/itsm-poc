#!/usr/bin/env bash
#
# Cross-deployable boundary check (T013, ADR-0001, constitution Principle V).
#
# RagCore and the .NET monolith have NO application-level dependency in either direction — no API
# call, no library reference, no deployment coupling. They meet at exactly two places: PostgreSQL,
# through versioned views RagCore owns, and Service Bus, through opaque triggers.
#
# No compiler catches this, because there is nothing to compile across the boundary. This script is
# what catches it, and it runs as a required CI check.
#
# Implementation note: plain `find` + `grep` only. An earlier version switched between ripgrep and
# grep depending on what was installed, and the two disagreed — it passed a planted violation.
# A guard that can silently stop guarding is worse than no guard, so this one has a single path.
#
# Second implementation note, learned the same way: THIS GUARD MUST NOT FIRE ON PROSE. Every check
# below either anchors at statement position or runs over comment-stripped lines, because a guard
# that flags the comment explaining the rule — or the test enforcing it — is a guard that gets
# suppressed, and then the rule has nothing behind it at all.
#
# Exit 0 = boundary intact. Exit 1 = violation(s), with the offending lines printed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

violations=0

# Collect source files under a tree, skipping build output and dependency directories.
sources() {
  local tree="$1"
  shift
  [ -d "$tree" ] || return 0
  local -a expr=()
  for ext in "$@"; do
    expr+=(-name "$ext" -o)
  done
  unset 'expr[${#expr[@]}-1]'
  find "$tree" \
    \( -path '*/bin/*' -o -path '*/obj/*' -o -path '*/node_modules/*' \
       -o -path '*/.venv/*' -o -path '*/dist/*' -o -path '*/.angular/*' \) -prune -o \
    -type f \( "${expr[@]}" \) -print 2>/dev/null
}

# Grep a pattern across a file list. Prints matches; returns 0 if any were found.
#
# Whole-line comments are dropped first. This is line-based rather than a real parser, so it does
# not understand a comment that trails code — which is the right trade here: a trailing comment
# cannot introduce a dependency, and a parser per language is what the in-language architecture
# tests are for.
scan() {
  local pattern="$1"
  shift
  local files
  files="$(cat)"
  [ -n "$files" ] || return 1
  printf '%s\n' "$files" | tr '\n' '\0' \
    | xargs -0 grep -nIE "$pattern" 2>/dev/null \
    | grep -vE '^[^:]+:[0-9]+:[[:space:]]*(//|\*|#)'
}

check() {
  local description="$1" pattern="$2" tree="$3"
  shift 3
  local hits
  hits="$(sources "$tree" "$@" | scan "$pattern")"
  if [ -n "$hits" ]; then
    printf '\n  \xe2\x9c\x97 %s\n' "$description"
    printf '%s\n' "$hits" | sed 's/^/      /'
    violations=$((violations + 1))
  fi
}

echo "Checking cross-deployable boundary (ADR-0001)..."

# ---------------------------------------------------------------- .NET -> RagCore
check ".NET build files reference RagCore" \
  'ragcore' dotnet '*.csproj' '*.sln' '*.props' '*.targets'

# A `using` directive or a URL naming the other deployable. NOT a bare word match: the
# architecture tests and their own documentation legitimately name RagCore in prose, and a guard
# that flags the test guarding it is a guard somebody disables.
check ".NET source has a using directive or URL naming RagCore" \
  '(^[[:space:]]*using[[:space:]]+[A-Za-z.]*[Rr]agcore|https?://[^"]*ragcore)' dotnet '*.cs'

# ---------------------------------------------------------------- RagCore -> .NET
# Anchored at statement position. An unanchored match hits docstrings that describe the rule -
# `"""No ``import Synthia...`` anywhere"""` is documentation, not an import.
check "RagCore imports a Synthia (.NET) module" \
  '^[[:space:]]*(from|import)[[:space:]]+Synthia([.[:space:]]|$)' ragcore '*.py'

# Dependency manifests only. Prose in .py files is handled by
# ragcore/tests/architecture/test_no_dotnet.py, which parses the AST and can tell a docstring from
# a string literal - a distinction grep cannot make.
check "RagCore declares a .NET dependency" \
  'Synthia\.(Api|Modules|Contracts|Persistence|SharedKernel|Observability)' ragcore '*.toml'

# --------------------------------------------- an HTTP client in either targeting the other
# Specification 13.4: there is no direct service-to-service path. A base address naming the other
# deployable is that path, however it is spelled.
check ".NET configures an HTTP client targeting RagCore" \
  '(BaseAddress|base_?[Uu]rl).{0,80}ragcore' dotnet '*.cs' '*.json'

check "RagCore configures an HTTP client targeting the monolith" \
  '(BaseAddress|base_?[Uu]rl).{0,80}(synthia-api|synthia\.api)' ragcore '*.py' '*.toml' '*.json'

# ------------------------------------- Integrations Service boundary (ADR-0007, spec 21.6)
# The Integrations Service is a THIRD deployable, parallel to RagCore. RagCore reaches it two ways
# and no other: synchronously through APIM, asynchronously over Service Bus. Neither imports the
# other.
#
# THIS IS THE ONE VIOLATION NO NETWORK OR GATEWAY CHECK COULD SEE, because an import never crosses
# a wire. The edge guard proves no direct HTTP route exists; only this proves no direct LINKAGE
# does.

check "Integrations imports RagCore" \
  '^[[:space:]]*(from|import)[[:space:]]+ragcore([.[:space:]]|$)' integrations '*.py'

check "RagCore imports the Integrations Service" \
  '^[[:space:]]*(from|import)[[:space:]]+integrations([.[:space:]]|$)' ragcore '*.py'

check "Integrations declares a RagCore dependency" \
  '^[[:space:]]*"?ragcore"?[[:space:]]*[=><~]' integrations '*.toml'

check "RagCore declares an Integrations dependency" \
  '^[[:space:]]*"?integrations"?[[:space:]]*[=><~]' ragcore '*.toml'

check ".NET build files reference the Integrations Service" \
  'synthia[._-]integrations' dotnet '*.csproj' '*.sln' '*.props' '*.targets'

# A SHARED LIBRARY IS THE SAME COUPLING WEARING A FRIENDLIER NAME. Constitution Principle VI:
# duplication across a boundary is cheaper than a false shared contract. The two services duplicate
# their correlation middleware, problem-details shape, settings base and telemetry setup on purpose,
# and the tempting fix — extracting `synthia_common` — would be a build-level dependency between
# deployables required to have none.
check "A shared Synthia Python package is imported" \
  '^[[:space:]]*(from|import)[[:space:]]+synthia(_common|_shared)?([.[:space:]]|$)' \
  integrations '*.py'

check "A shared Synthia Python package is imported by RagCore" \
  '^[[:space:]]*(from|import)[[:space:]]+synthia(_common|_shared)([.[:space:]]|$)' ragcore '*.py'

# Specification 13.4 again: a base address naming the other deployable is a direct route, however it
# is spelled. RagCore reaches Integrations through APIM or not at all.
check "RagCore configures an HTTP client targeting Integrations directly" \
  '(BaseAddress|base_?[Uu]rl).{0,80}synthia[._-]integrations' ragcore '*.py' '*.toml' '*.json'

check "Integrations configures an HTTP client targeting RagCore" \
  '(BaseAddress|base_?[Uu]rl).{0,80}(ragcore|synthia-api|synthia\.api)' \
  integrations '*.py' '*.toml' '*.json'

# THE INTEGRATIONS SERVICE DOES NO REASONING (FR-INTEG-007). It reaches no model provider and no AI
# Gateway; model egress and content safety stay in RagCore because they are reasoning, not
# integration. A model client here would be a second, ungoverned model egress outside the AI
# Gateway's metering, budgets and content safety.
check "Integrations declares a model or graph dependency" \
  '^[[:space:]]*"?(langgraph|openai|azure-ai-[a-z]+|anthropic)' integrations '*.toml'

# ------------------------------- RagCore reaches NO external system (ADR-0007, spec 22.1, 23.1)
# The connectors moved. What must not come back is a module in RagCore that talks to a customer
# system directly - the blast radius that motivated the split is an orchestrator compromise
# yielding every organisation's connector credentials.
#
# THIS LIST WIDENS AS EACH CONNECTOR RELOCATES, AND IT IS DELIBERATELY NOT COMPLETE YET.
#
# ServiceNow has moved (this slice). Microsoft Graph, the MCP client, OneLogin and Duo have not -
# they relocate in the remaining Phase 16 tasks. Listing them here now would fail the build on work
# that has not been scheduled yet, and a guard that fails for work-in-progress is a guard somebody
# comments out. Each relocation adds its name below in the same change that removes its code.
#
# Anchored on IMPORT and on a MODULE PATH rather than on the vendor's name in prose: RagCore
# legitimately names ServiceNow throughout its documentation, its ports and its tests, and a guard
# that flagged those is a guard somebody disables.
check "RagCore imports the removed ServiceNow connector" \
  '^[[:space:]]*(from|import)[[:space:]]+ragcore\.integrations\.servicenow' \
  ragcore '*.py'

# A ServiceNow base address anywhere in RagCore. `integrations/model/` remains the one permitted
# egress - the AI Gateway - and it is untouched by naming the connector rather than excluding a path,
# because an exclusion is what somebody widens.
check "RagCore configures a ServiceNow endpoint" \
  '(instance_url|base_?[Uu]rl|BaseAddress).{0,60}service-?now' \
  ragcore '*.py' '*.toml' '*.json'

# ------------------------------------------- the monolith owns no schema (ADR-0001, ADR-0003)
#
# Scoped to dotnet/src, and that is the same deferral this script already makes for RagCore prose
# above. dotnet/tests/Synthia.ArchitectureTests/NoMigrationTests.cs names these APIs in a string
# array — it is the test that ENFORCES this rule, and it strips comments before matching so it can
# tell the rule from a description of it. grep cannot tell a call from a string literal; that test
# can, so the .cs enforcement is its job and this check guards the shipping code.
check ".NET calls a schema-owning EF API - Alembic owns every migration" \
  '(Database\.Migrate|EnsureCreated)[[:space:]]*\(' dotnet/src '*.cs'

migration_dirs="$(find dotnet -type d -name Migrations \
  \( -path '*/bin/*' -o -path '*/obj/*' \) -prune -o -type d -name Migrations -print 2>/dev/null)"
if [ -n "$migration_dirs" ]; then
  printf '\n  \xe2\x9c\x97 %s\n' ".NET contains an EF Migrations directory - the monolith owns no schema"
  printf '%s\n' "$migration_dirs" | sed 's/^/      /'
  violations=$((violations + 1))
fi

# ---------------------------------------------------------------- result
if [ "$violations" -gt 0 ]; then
  printf '\nBoundary check FAILED with %d violation(s).\n' "$violations"
  echo "RagCore and the monolith meet only at PostgreSQL (versioned views) and Service Bus (opaque"
  echo "triggers), with no application dependency in either direction. RagCore reaches the"
  echo "Integrations Service only through APIM and Service Bus, and the Integrations Service never"
  echo "calls back. If a dependency here is genuinely needed it requires an ADR amending ADR-0001"
  echo "or ADR-0007 - not a suppression here."
  exit 1
fi

printf '  \xe2\x9c\x93 No cross-deployable dependency found.\n'
printf '  \xe2\x9c\x93 No shared Python package between the two services.\n'
printf '  \xe2\x9c\x93 Integrations declares no model or graph dependency.\n'
printf '  \xe2\x9c\x93 The monolith owns no schema.\n'
exit 0
