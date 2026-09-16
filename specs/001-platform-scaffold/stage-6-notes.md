# Stage 6 Implementation Notes

**Date**: 2026-09-16 · **Scope**: Phase 6 (T069–T081) — the RagCore FastAPI application and
LangGraph skeleton, plus the PostgreSQL checkpointing **boundary** from T084. No business use
case, no product behaviour, no real integration, no autonomous ITSM operation.

**Gates**: `ruff check` clean, `ruff format --check` clean, `mypy --strict` clean across 107
source files, 311 tests passing.

## Three design errors found by writing the tests

All three passed review as prose and failed as soon as something exercised them. They are recorded
because the fix in each case is a *different rule*, not a patch.

### 1. A write-once `governance` channel made resume unreachable

The first reducer for the graph's `governance` channel sealed it outright: one write, any
differing second write raises. It reads correctly — "a treatment, once assigned, cannot be
revised" — and it broke the approval path completely.

The gate is **deliberately re-evaluated after a suspension**. `await_approval` routes back to
`govern`, not forward to `execute`, so a resumed run re-reads the durable decision and re-runs the
gate against the current tenant status and clock. That re-run is exactly how `suspend_for_approval`
becomes `proceed`. Sealing the channel made the second evaluation raise on every resume.

Second attempt: seal the `treatment` field, let the rest advance. That failed too, on a case that
is not hypothetical — a capability de-entitled while work waits produces `NOT_ALLOWED` on the next
evaluation, which is the **correct governance outcome** and was being reported as a crash.

The rule that actually holds is `domain.governance.is_narrowing`: **a treatment may become
stricter, never more permissive.** Suspension and de-entitlement both narrow, and both are
refusals. Widening is the failure the gate exists to prevent, whatever produced it.

The same ordering now backs `governance.policy._narrowed`, so policy and state cannot disagree
about what a safe re-assignment is. `test_graph_state.py::test_narrowing_agrees_with_the_policy_module`
asserts the two agree over all sixteen pairs.

### 2. `X-Tenant-Id` walked straight through the identity middleware

`FORBIDDEN_CLIENT_FIELDS` contained `tenantid`, and the normaliser folded case and separators —
so `tenant_id` and `tenantId` were caught and `X-Tenant-Id` was not. It folds to `xtenantid`.

That is the *conventional* spelling for a custom header and therefore the first thing anyone would
try. The fix folds the leading `x` as well, so one entry covers every spelling rather than the list
needing a prefixed and an unprefixed form of everything — where the one somebody forgets is the one
that gets through.

Found by `test_a_self_asserted_header_is_rejected`, which was written to be boring.

### 3. `Command(resume={})` resumes nothing

Not a defect in this codebase, but it cost an hour and will cost the next person the same. LangGraph
reads an **empty dict** as an empty resume *map* — a mapping of interrupt id to value — and resumes
no interrupt at all. The graph silently re-interrupts and the run looks stuck.

Recorded on `WAKE` in `test_graph_interrupts.py`, where a resume payload is needed and its contents
are deliberately meaningless.

## Where the authority rule became structural

The brief's central requirement — **MODEL MAY PROPOSE, MODEL MAY NOT AUTHORIZE** — is enforced in
five independent places. No one of them is load-bearing alone.

| Mechanism | Where | What it makes impossible |
|---|---|---|
| A proposal has no `treatment` field | `domain/proposal.py` | The model has nowhere to write an authorization |
| The gate has no `treatment` parameter | `governance/gate.py` | A caller cannot pass one in "from the catalogue" |
| The state channel has no `treatment` key | `graph/state.py` | A checkpoint cannot carry one |
| Two decision types, not one with a `kind` | `domain/decisions.py` | Consent cannot satisfy staff approval — the branch takes the wrong type |
| The treatment may only narrow | `domain/governance.py` | A second evaluation cannot loosen the first |

Plus one at the point of effect: `execute` re-reads the gate's own disposition and raises without
`PROCEED`, **redundantly with the routing**. Routing decides which node runs; that check decides
whether the node does anything. A graph edited to reach execution some other way still does not
execute.

`tests/governance/test_authority_boundary.py` (54 tests) asserts all of it, including exhaustive
sweeps over both source enumerations — so a new content class added without a classification fails
there rather than defaulting to unauthorized and never being noticed.

## Two choices that diverge from the obvious implementation

### The graph state is JSON-native, not domain objects

`AgentState` holds `TypedDict`s of primitives and `Literal`s rather than domain types. Domain
objects *do* round-trip through LangGraph's serializer — but only with each type registered in a
msgpack allowlist that then has to stay correct across every deployment, and the current version
already warns that unregistered types will be blocked.

Primitives carry the same information with no allowlist and no way for a checkpoint written last
month to fail to load. `graph/projections.py` converts, through mappings that
`test_graph_state.py` proves total over their enums — so adding a domain enum member without adding
it to the mirror fails a test rather than raising `KeyError` on the one path that reaches the new
case.

### The tenant is run context, not state

`RunContext` carries `TenantContext`; the checkpoint carries only an opaque `tenant_id` string.

`TenantContext` is constructible only through classmethods that name their provenance, and there is
deliberately no `from_request`. If the tenant travelled in the checkpoint, resuming would mean
rebuilding that context from a value that has lost its provenance — and the only way to do so would
be to add the constructor the domain refuses to have. Carrying it as run context means the binding
is re-established from a trusted source on every invocation, and no node has a channel to write it.

## Partially delivered, deliberately left unchecked

**T084** and **T111** remain `[ ]`. What exists:

- `graph/checkpointer.py` — the durable boundary. `AsyncPostgresSaver` against the `langgraph`
  schema, pinned by `search_path` on the connection (the saver takes no schema argument), with
  `provision_checkpoint_schema` separate from `durable_checkpointer` so the runtime path has no
  `setup()` to call by accident.
- `tests/checkpoint/test_durable_checkpointer.py` — 13 structural tests: no foreign durable saver
  anywhere, the Postgres saver constructed in exactly one module, no in-memory saver on a
  non-test path, DDL confined to the provisioning entry point.

What does not: **the application does not compile the graph against it**, because the container
binds no repositories and there is nothing to run. T084's "compile the graph with it in place of
the in-memory saver" and T111's "the compiled graph carries the PostgreSQL saver" both land at
Stage 7, with the adapters. Marking them done would claim a wiring that is not there.

`psycopg[binary]` was added to `pyproject.toml`. `langgraph-checkpoint-postgres` needs a libpq
binding and the lock had only the pure-Python `psycopg`, so importing the saver failed outright.

`src/ragcore/py.typed` was added. Without it, `mypy` resolving `ragcore` as an installed package —
which it does whenever invoked on a subpath rather than the configured `files` list — treated every
first-party import as untyped and produced 112 spurious errors.

## Deferred

| Area | Lands at |
|---|---|
| Alembic, migrations, every table and view | Stage 7 (T082–T110) |
| Repositories, and the adapters the container binds `None` for | Stage 7–9 |
| Outbox, publisher, resume worker, expiry sweeper | Stage 8 |
| Model access through the AI Gateway | Stage 9 (T127, T128) |
| The catalogue's four reference fixtures | Stage 11 |
| The two golden paths | Stages 12–13 |
| UC-01..UC-12 | Stage 14, gated behind both golden paths |

**No business use case was implemented.** Every route that would record a decision returns 501
rather than a plausible success; the container binds only the clock; `ToolExecutionPort` has no
adapter, so nothing in the scaffold can perform an ITSM operation even if something reached the
execution node.
