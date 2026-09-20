---
name: "langgraph-change"
description: "Run the mandatory ordered procedure for any change to the LangGraph workflow - nodes, edges, routing, topology, state, interrupts, resume, execution ordering, termination, checkpoint persistence or side-effect boundaries: detect, stop, describe, classify workflow-only vs architecture-changing, obtain explicit approval, require an accepted ADR first when architecture or authority changes, then implement, test and verify."
argument-hint: "The graph change being requested"
user-invocable: true
disable-model-invocation: false
---

# LangGraph change procedure

Governing rule: `.claude/rules/30-langgraph.md`. The rule says **what must be true**; this skill is
**how to do it, in order**. The order is the governance.

Invoke this skill before editing anything under `ragcore/src/ragcore/graph/`, and before editing
resume servicing wherever it lives.

---

## Step 1 — DETECT

Does the requested change alter LangGraph behavior? It does if it touches **nodes**, **edges**,
**routing**, **topology**, **state shape**, **state semantics**, **interrupts**, **resume behavior**,
**execution ordering**, **termination behavior**, **clarify-loop behavior**, **retrieval routing**,
**resolution routing**, **approval flow**, **execution treatment**, **checkpoint persistence**, or
**side-effect boundaries**.

How to check rather than guess:

1. `ragcore/src/ragcore/graph/builder.py` — the node registrations and the edge/routing topology.
2. `ragcore/src/ragcore/graph/state.py` — the state fields, typed records and reducers.
3. `ragcore/src/ragcore/graph/nodes/` — the node contracts.
4. `ragcore/src/ragcore/graph/checkpointer.py` — the durable checkpoint boundary.
5. `ragcore/workers/resume_worker.py` — non-live resume servicing.

If nothing in Step 1 is touched: say so in one line and continue with ordinary implementation.
Otherwise go to Step 2. Uncertainty resolves toward yes.

## Step 2 — STOP

Stop implementation. Do not open the graph modules for editing yet, and do not write "a small
node-local change first". A graph change that is discovered mid-edit stops at that point and restarts
at Step 1.

## Step 3 — DESCRIBE

State each of the following, or "none":

```markdown
### LangGraph change impact

- Nodes:                 <added / removed / contract changed>
- Edges:                 <added / removed / redirected>
- Topology:              <entry, terminal edges, subgraph structure>
- State fields:          <added / removed / renamed / retyped, and reducer changes>
- State semantics:       <what a field now means, who may write it>
- Interrupts:            <added / removed, and transport>
- Resume behavior:       <live and non-live>
- Routing:               <which predicate, which branches>
- Execution ordering:    <including what is re-read before a consequential action>
- Termination:           <which branches are terminal>
- Checkpoint persistence:<impact, or none>
- Authority behavior:    <anything in rule 30.3 affected?>
- Side effects:          <any node gaining, losing or moving a side effect?>
```

## Step 4 — CLASSIFY

Decide, explicitly, which of two kinds this change is:

**(a) Workflow-only** — it changes graph behavior without changing architecture or an architectural
rule. It leaves every protection in rule §30.3 intact: the LLM gains no execution authority; no
agent node gains a side effect; tenant, requester, approval and execution identity still come from
trusted context and the durable work item; execution still re-reads authoritative durable state
before acting; no untrusted channel can widen authority.

**(b) Architecture/authority-changing** — it touches any item in `.claude/rules/30-langgraph.md`
§30.4: execution authority, side-effect boundaries, `execution_treatment` semantics, approval
semantics, the approval suspend/resume model, verdict source, approval binding, the no-timeout
approval lifecycle, signed/idempotent execution, typed resolution, SOP terminality, the two-index
retrieval architecture, field-scoped embedding, memory architecture, per-tenant tool injection,
mandatory tenant filtering, or evaluation release-gate thresholds.

Say which one it is and why. If it is genuinely ambiguous, treat it as (b).

A checkpoint-persistence change is additionally a **database** change: go to `db-change` now and
follow Step 10 below.

## Step 5 — APPROVE

- Present the Step 3 description and the Step 4 classification, and ask for explicit approval.
- **Wait.** Implementation stops until approval arrives. Approval is explicit human assent in this
  session about this change; it is never inferred from an accepted plan, a prior approval, silence,
  the permission mode, or a satisfied hook.
- This skill never approves the change.

## Step 6 — ADR (only for classification (b))

If the change is architecture/authority-changing:

1. The ADR comes **before** the implementation — not concurrent, not retrospective.
2. Write it in MADR format under `docs/adr/`, continuing the sequential numbering, with a status
   field.
3. It states the architectural rule being changed, the owning document and section, the alternatives,
   and the consequences for the execution-authority boundary.
4. **Do not create the ADR and then continue as though it were accepted.** Human acceptance is a
   separate event and is required. Stop after writing it.
5. If acceptance is refused, the implementation does not happen; return to Step 3 with a different
   design.

## Step 7 — IMPLEMENT

Only after approval, and after ADR acceptance where Step 6 applied:

- Implement exactly the change that was described and approved. A change discovered to be larger
  than described returns to Step 3.
- Keep the protections in rule §30.3 intact in the code as written, not merely in intent.
- Do not add state fields that were not in the approved description.

## Step 8 — TEST

- Run the existing suites under `ragcore/tests/` — graph, checkpoint, governance, idempotency,
  authorization, isolation, architecture, contracts: `uv run pytest -q` from `ragcore/`.
- Test topology and routing changes at the graph level, not only per node.
- An authority-bearing change is checked against the suite that asserts the authority rule.
- **Never weaken a test to make the change pass** — no deletion, no `skip`/`xfail`, no loosened
  assertion, no narrowed fixture.

## Step 9 — VERIFY

Confirm and state:

- the implemented change matches the Step 3 description, field for field;
- the classification in Step 4 still holds after implementation;
- every protection in rule §30.3 is still true of the code;
- tests pass and none was weakened;
- where Step 6 applied, the accepted ADR is referenced.

If any of these fails, the change is not done. Say so.

## Step 10 — When checkpoint persistence is involved

Database governance takes ordering precedence over this procedure:

```text
Detect the DB change -> stop -> describe the DB impact -> obtain approval
                     -> implement and validate the DB change
                     -> only then continue the LangGraph implementation.
```

Graph code is not changed first merely because the graph change was the original request. Run the
`db-change` skill to completion through its validation step, then return here at Step 7.

## What this skill must never do

- Approve the change, or accept its own ADR.
- Implement before approval, or before ADR acceptance where one is required.
- Reduce an §30.4 condition to a generic "ask for approval".
- Weaken, skip or delete a test.
- Change graph code ahead of a required database change.
- Fix an architecture-vs-implementation deviation it happens to notice. Report it instead.
