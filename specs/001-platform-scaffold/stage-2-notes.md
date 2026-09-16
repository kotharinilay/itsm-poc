# Stage 2 Implementation Notes

**Date**: 2026-09-16 · **Scope**: Phase 2 (T023–T037) — shared contracts and architecture
boundaries. No business use case, no product behaviour, no real integration.

## Two design decisions worth reviewing

Both are choices rather than transcription, and both are asserted by tests so they cannot drift
back.

### 1. `StaffRole` is not an enum in either stack

The obvious implementation is an enum. It is wrong in both languages, for the same reason and with
two different symptoms:

| Stack | The trap | What was built |
|---|---|---|
| C# | An enum is integer-backed, so `IComparable`, `<` and `>` come for free — the exact ranking Principle II prohibits | `readonly record struct` with equality and nothing else. `role1 < role2` **does not compile** |
| Python | `StrEnum` and `IntEnum` inherit an ordering from their mixin, so `ADMINISTRATOR > TECHNICIAN` silently evaluates | Plain `Enum`, which raises `TypeError` on `<` |

Asserted by `RoleIntersectionTests.Staff_role_is_not_an_enum` and
`test_roles.py::test_roles_cannot_be_compared`. If someone "simplifies" either type to an enum,
those fail.

### 2. Authorization and treatment policy are **not** ports

The task brief listed authorization among the infrastructure boundaries. It was implemented as a
pure domain function instead, and `TestAuthorizationIsNotAPort` asserts that no
`AuthorizationPort` exists.

The reasoning: `evaluate(principal_roles, accepted_roles)` needs no database, no clock and no
configuration. Making it injectable would permit an implementation that consults one — and the
moment authorization can consult infrastructure, a role or a treatment can arrive from somewhere
that is not the catalogue. The same argument applies to treatment policy: the **catalogue** is a
port because entries are stored; the **decision** is not, because injectability is precisely how a
model-supplied treatment would get in.

Ports were created for the twelve genuine infrastructure boundaries: clock, tenant registry, five
repositories, unit of work, operation catalogue, retrieval, idempotency store, tool execution,
outbox, message publisher, notification, audit sink, model, ingestion.

## Where the rules became structural rather than remembered

Three places where the type system does the enforcing, rather than a reviewer:

- **`AuthenticatedPrincipal.AuthorizableRoles`** returns `{end_user}` on the customer audience,
  regardless of what the principal holds. Staff roles are not consulted on a customer surface
  (Principle II) — not because every call site remembers, but because the set they would consult
  does not contain them.
- **`TenantContext` has no public constructor.** It comes only from `TenantAdmission`, whose three
  methods each name their provenance: admitted identity, work item, platform object. There is
  deliberately no `FromRequest`, no `FromHeader`, no `Parse`. A caller holding a client-supplied
  tenant identifier has nowhere to go, which is the intended outcome.
- **Every repository port takes `TenantContext` as a required first parameter.** There is no
  overload that omits it, so "no query path omits the tenant filter" is a property of the interface
  rather than a rule each implementation is trusted to follow.

## A guard that did not work, again

`ModuleIsolationTests` was first written to reflect over compiled metadata:
`Assembly.GetReferencedAssemblies()`. **It passed a planted module-to-module reference.**

`GetReferencedAssemblies()` reports the references the compiler actually *emitted*, and the C#
compiler omits a reference whose types are never used. A module that declares a `ProjectReference`
on another module but has not used it yet is therefore invisible to reflection — which is exactly
the state a boundary breach passes through on its way in: **the reference is added first, the
coupling follows.**

Rewritten to parse the `.csproj` files directly (`ProjectGraph`), which catches the declaration at
the moment it is added. The metadata check is retained as a second layer: it catches an
actually-used reference arriving by some route other than a `ProjectReference`. Neither test makes
the other redundant, and the reasoning is recorded in `ProjectGraph`'s own header because the
tempting "cleanup" is to delete one.

This is the second guard in two stages that did not work when first written, and both were found
the same way — by planting the violation. `build/scripts/verify-architecture-guards.sh` now does
that automatically, in CI, for all six violation classes.

## Boundary check: prose matching replaced with structural matching

Adding the architecture tests broke `check-boundaries.sh` with **seven false positives** — every
one a comment, docstring, or the guard test itself. `NoRagCoreDependencyTests.cs` contains the word
"ragcore" because that is what it forbids.

A guard that flags the test guarding it is a guard somebody disables, so the fix was precision
rather than a blanket exclusion:

| Check | Before | After |
|---|---|---|
| .NET → RagCore | bare word `ragcore` anywhere in a `.cs` file | a `using` directive or an `http(s)://…ragcore` URL |
| RagCore → .NET import | `(import\|from)\s+Synthia` anywhere in a line | anchored at statement position, `^\s*(from\|import)\s+Synthia` |
| RagCore names an assembly | any `.py` or `.toml` | `.toml` only — dependency manifests |

Prose in `.py` files is now handled by `test_no_dotnet.py`, which parses the AST and can tell a
docstring from a string literal. Grep cannot make that distinction; a parser can. **The split is
the point:** the shell script checks what a shell script is good at — structure — and the
architecture tests handle what needs a parser.

All four boundary plants still fail correctly after the change.

## Deferred

| Area | Lands at |
|---|---|
| EF Core read contexts over `vw_*_v1` views | Stage 7 (T108) |
| Middleware consuming `PrincipalFactory` | Stage 5 (T057) |
| Adapters implementing every port | Stage 9 |
| Governance treatment policy over the catalogue | Stage 11 (T153, T154) |
| Per-resource `QueryWhitelist` instances | Stage 5 (T062), against `contracts/README.md` |

**No business use case was implemented.** Every port is a Protocol or interface with no
implementation; the catalogue port returns entries but no catalogue exists; `ExecutionTreatment`
has four members and no policy assigns them yet.
