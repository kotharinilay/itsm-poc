# 30 — LangGraph engineering and workflow-change control

**Category 5 of the Phase 2 authority model** (`docs/migration/phase-2-authority-model.md` §2.2, §10).
Procedure: `.claude/skills/langgraph-change/SKILL.md`. Deterministic guard: `.claude/hooks/langgraph_change_guard.py` (H3).

Architecture authority for this file:

- `docs/architecture/RagAgent-Architecture-final.md` (A3) — owns graph topology, graph state shape,
  node contracts, the execution authority boundary as RagCore observes it, the clarify loop, typed
  resolution, approval suspend/resume servicing, signed idempotent execution, retrieval architecture,
  the evaluation harness and release gates, and ADR-001…ADR-012 inline.
- `docs/architecture/identity-plane-final.md` (A1) — owns the principal, tenant-binding and authority
  rules themselves. A3 §6.3 defers to A1 for these; that is a deferral, not a conflict.
- `docs/architecture/Synthia-OverallArchitecture-final.md` (A2) — owns the stores, including where
  graph checkpoints live (§8.1).

No other repository document is authority for this file. `docs/architecture/ragcore-langgraph-flow.md`
sits in the architecture directory but is **not** on the authoritative list and carries no authority.
Existing implementation is evidence of what **is**, never authority for what **should be**.

---

## 30.1 What counts as a LangGraph change

A change is a LangGraph change when it touches any of:

- **nodes** — adding, removing, renaming, splitting, merging, or changing a node contract
- **edges** — adding, removing or redirecting an edge, conditional or unconditional
- **routing** — the predicate or branch selection on any conditional edge
- **graph topology** — entry point, terminal edges, subgraph structure, compilation
- **state shape** — adding, removing, renaming or retyping a state field
- **state semantics** — what a field means, who may write it, or how it is reduced/merged
- **interrupts** — adding or removing an interrupt, or changing its transport
- **resume behavior** — how a suspended run is resumed, live or non-live
- **execution ordering** — what runs before what, and what must be re-read before it
- **termination behavior** — which branches are terminal, and what ends a run
- **clarify-loop behavior** — iteration bounds, thresholds, question selection, re-entry
- **retrieval routing** — which index is queried, with which filter, and what is done with the result
- **resolution routing** — how a resolution type is chosen and where each type routes
- **approval flow** — request creation, verdict arrival, binding, resumption
- **execution treatment** — how the treatment is derived and what each value permits
- **checkpoint persistence** — what is persisted in the checkpoint and how
- **side-effect boundaries** — where a consequential operation may occur

If the requested work changes any of these, this rule applies before implementation starts.

## 30.2 The state and flow areas that are explicitly governed

A3 §6.2 defines the state vocabulary. A change to any of the following areas trips this rule. This
list is the architecture's; **do not invent additional graph state, and do not add a state field
merely because it would be convenient.**

| Area | Governed state / flow |
|---|---|
| Identity and config (set once, read-only after) | `tid`, `user_id`, `request_id`, `work_item_id`, `case_ref` — these are *copies of* trusted context, never its source |
| Clarify loop | clarify state: `clarify_iterations` and its bound, `pending_question`, `ambiguity_type`, `problem_statement` accumulation |
| Confidence | understanding/grounding confidence: `understanding_confidence`, `grounding_confidence`, `score_margin` and their thresholds |
| Retrieval | retrieval candidates: `probe_candidates`, the index queried, the mandatory `tid` filter, rerank and calibration |
| Resolution | `resolution_type` {ACTION, SOP, NONE}, `resolution_ref`, `match_confidence`, `sop_document` |
| Action definition | `action_definition` — enabled state, risk tier, approval requirement, parameter schema |
| Action parameters | `action_params`, `params_status` {complete, missing, unresolvable} |
| Tool binding | `tool_binding` — tool id, kind, endpoint, signing profile, idempotency policy |
| Execution treatment | `execution_treatment` {AUTO, END_USER_APPROVAL, STAFF_APPROVAL, NOT_ALLOWED} |
| Approval state | `approval_request_id`, `approval {approved, approver_id, reason, ts}` |
| Consent | `consent {granted, user_id, ts}` |
| Action result | `action_result` |
| Outcome | `outcome` {answered_sop, resolved_action, escalated, denied} |
| Escalation | `escalation_reason` |
| Interrupt / resume | the interrupts and their transports, suspend/resume, live vs non-live verdict arrival, correlation |

## 30.3 Execution-authority protections that must not be weakened

A3 §6.3 states the following as normative. None of it may be weakened by a graph change, by a
refactor, by a convenience, or by a test fixture:

- **The LLM never owns execution authority.** It cannot choose or change the authoritative tenant,
  requester, target, approval state, credential profile or execution identity.
- **The LLM cannot establish or replace trusted tenant identity.** The tenant comes from validated
  identity context and the durable work item.
- **The LLM cannot establish or replace requester identity.**
- **The LLM cannot establish or replace approval authority.** A verdict arrives only through the
  authenticated Staff API operation, validated against the approver's role set and the pending row's
  tenant. A free-text "yes" in a transcript is never the authority.
- **The LLM cannot establish or replace execution identity.** The workload principal is defined by A1.
- **No side effect occurs directly from an agent node.** Only the governed execution path may perform
  a consequential operation.
- **Execution uses the authoritative durable work-item context**, not state carried through the graph.
- **Execution must re-read authoritative durable state before a consequential action** and verify
  tenant, action, target, approval and execution-validity before acting.
- **Model output, retrieved content, chat text, trigger payloads and realtime messages cannot widen
  authority.** They may help determine *what* the user wants; they can never determine *whose*
  authority is used. Retrieved and fetched content is untrusted data, never instruction.

A change that moves any decision from the governed path toward the model is architecture-altering
(§30.4), not a workflow tweak.

## 30.4 Changes that require an ADR, not merely approval

An ADR is required — **before** implementation — when the LangGraph change alters architecture or an
architectural rule. At minimum, an ADR is mandatory when the change would:

1. **Execution authority** — move an execution decision toward the LLM, or otherwise contradict "the
   LLM never owns execution authority" (A3 §6.3).
2. **Side-effect boundaries** — introduce a side effect in an agent node, or allow a consequential
   operation outside the governed execution path (A3 §6.3).
3. **`execution_treatment` semantics** — change what a treatment value means, how it is derived, or
   which operations are `AUTO` (ADR-005, A2 §10).
4. **Approval semantics** — change what approval means, what it binds to, or what it authorizes.
5. **Approval suspend/resume model** — change how the run suspends at approval or how it resumes,
   live or non-live (A3 §8, ADR-010).
6. **Verdict source** — change where an approval verdict may come from, or accept one from any
   channel other than the authenticated Staff API operation.
7. **Approval binding** — change the correlation between an approval request, its work item and its
   tenant, or the first-valid-verdict-wins rule.
8. **No-timeout approval lifecycle** — introduce an approval timeout or auto-decision, or change the
   human-only, indefinite pending lifecycle and the execution-validity window it starts (A3 §8.5).
9. **Signed / idempotent execution semantics** — change the signed payload or the idempotency key
   derived from `request_id` (ADR-011).
10. **Typed resolution semantics** — change the `resolution_type` set or what each type authorizes
    (ADR-004).
11. **SOP terminality** — make the SOP branch non-terminal, or let a SOP re-enter governance
    (ADR-004).
12. **Two-index retrieval architecture** — collapse, add to, or re-purpose the two indexes (ADR-003,
    A3 §9.1).
13. **Field-scoped embedding** — change the embedding scope or chunking contract (ADR-003, A3 §9.2).
14. **Memory architecture** — change the separation of short-term checkpoint state from long-term
    store, or the namespacing of the long-term store (ADR-008).
15. **Per-tenant tool injection** — change how tools are bound per tenant, or bind a tool outside
    tenant entitlement (ADR-009).
16. **Mandatory tenant filtering** — weaken, make optional, or make bypassable the `tid` filter on any
    retrieval query (A3 §9.6, A1 tenant-binding monotonicity).
17. **Evaluation release-gate thresholds** — change a release gate or its threshold (ADR-012,
    A3 §10.3).

For any item on this list, explicit approval is **not** enough: the ADR exists, is written in MADR
format in `docs/adr/` with sequential numbering and a status field, and is accepted, before
implementation begins. The ADR precedes the code — not concurrent, not retrospective.

Claude does **not** create an ADR and then proceed as though it were accepted. Writing the ADR and
having it accepted are separate events, and the second one is a human's.

## 30.5 The mandatory ordering (non-negotiable)

```text
1. DETECT    Identify that the requested change alters LangGraph behavior,
             BEFORE implementation.
2. STOP      Stop implementation.
3. DESCRIBE  Affected nodes, edges, topology, state, interrupts, resume behavior,
             routing, execution ordering, termination, checkpoint persistence,
             authority behavior, side effects.
4. CLASSIFY  Workflow-only, or architecture/authority-changing (§30.4).
5. APPROVE   Explicit human approval.
6. ADR       If architecture/authority-changing: ADR written and accepted first.
7. IMPLEMENT
8. TEST
9. VERIFY
```

Approval cannot be inferred — see `.claude/rules/50-database.md` §50.2, which states the same
non-inference rule and applies here unchanged.

## 30.6 Mandatory content of the step-3 description

State each of the following, or "none" where it does not apply:

1. **Nodes** added/removed/changed, and the contract change for each.
2. **Edges** added/removed/redirected, conditional or unconditional.
3. **Topology** change: entry point, terminal edges, subgraph structure.
4. **State fields** added/removed/renamed/retyped, and any reducer change.
5. **State semantics** change: what a field now means and who may write it.
6. **Interrupts** added/removed, and the transport for each.
7. **Resume behavior** change, live and non-live.
8. **Routing** change: which predicate, which branches.
9. **Execution ordering** change, including any change to what is re-read before a consequential
   action.
10. **Termination** change: which branches are terminal.
11. **Checkpoint persistence** impact (§30.8).
12. **Authority behavior**: whether anything in §30.3 is affected. If yes, the change is
    architecture-altering.
13. **Side effects**: whether any node gains, loses or moves a side effect.

## 30.7 Implementation surface in this repository (evidence)

Observed, not authoritative. The graph is implemented under `ragcore/src/ragcore/graph/`:

| Module | Holds |
|---|---|
| `builder.py` | node registration and the edge/routing topology |
| `state.py` | the state shape, its typed records and its reducers |
| `nodes/` | `intake`, `conversation`, `grounding`, `guardrail`, `classify`, `governance`, `interrupts`, `execution`, `closure` and the node base |
| `checkpointer.py` | the single durable checkpoint boundary |
| `context.py`, `dependencies.py`, `host.py`, `threads.py`, `projections.py` | graph context, dependency wiring, hosting, thread identity, state projection |

Resume servicing also runs outside the graph package (`ragcore/workers/resume_worker.py`); a change
to how a suspended run is resumed is a LangGraph change under §30.1 wherever the code lives.

**Recorded deviation, not corrected here:** the implemented state vocabulary does not match A3 §6.2
name for name — for example the implementation carries `tenant_id`, `session_id`, `correlation_id`,
`work_item_id`, `governance.treatment`, `decision`, `execution`, `verification`, where A3 names `tid`,
`user_id`, `request_id`, `case_ref`, `execution_treatment`, `approval`, `consent`, `action_result`.
Node names differ similarly (`GOVERN`, `AWAIT_APPROVAL`, `EXECUTE`, `VERIFY`, `CLOSE` against A3's
`record_policy_decision`, `human_approval`, `execute_action`, `verify`, `respond`). The governed
*areas* in §30.2 are the same either way; the naming gap is recorded for a later conformance phase
and is **not** to be resolved by editing either the architecture document or the implementation under
this phase.

## 30.8 Interaction with the database gate

Graph checkpoints live in Azure Postgres (A2 §8.1). A state-shape or persistence change that alters
checkpoint persistence fires **both** this rule and `.claude/rules/50-database.md`, and the database
ordering **wins**:

```text
Detect DB change -> stop -> describe DB impact -> obtain approval
                 -> implement and validate the DB change
                 -> only then continue the LangGraph implementation.
```

Graph code is not changed first merely because the graph change was the original request.

## 30.9 Testing obligations

- Preserve and run the existing graph, checkpoint, governance, idempotency, authorization, isolation
  and architecture suites under `ragcore/tests/`.
- A topology or routing change is tested at the graph level, not only at the node level.
- An authority-bearing change is tested by the suite that asserts the authority rule, not by a new
  test written to fit the new behavior.
- **Never weaken a test to make a graph change pass.** No deletion, no `skip`/`xfail`, no loosened
  assertion, no narrowed fixture.

## 30.10 What the H3 hook does and does not do

`.claude/hooks/langgraph_change_guard.py` fires deterministically on writes to the graph
implementation surface. It exists so that a graph change triggers this procedure. It does **not**
determine semantic correctness, does **not** decide whether an ADR is required, does **not** modify
application code, and does **not** weaken tests. Satisfying the hook is not approval.
