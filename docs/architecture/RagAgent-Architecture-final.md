# ITSM Self-Service Agent — RAG & Agentic Architecture

**Synthia / CommandCenter — Multi-Tenant Agentic ITSM on Azure**

| | |
|---|---|
| **Author** | Gitesh Tripathi — CTO, Synoptek |
| **Platform** | Synthia / CommandCenter (Azure) |
| **Document** | RAG & Agentic Architecture — ITSM Self-Service Resolver |
| **Version** | 1.1 |
| **Date** | 4 September 2026 |
| **Classification** | Confidential — Internal |
| **Status** | Draft for review |
| **Aligned** | 15 September 2026 — reconciled against the Platform Functional & Architecture Specification |

---

## Contents

- [1. Purpose & Thesis](#1-purpose-thesis)
- [2. Scope & Context](#2-scope-context)
- [3. Architectural Principles](#3-architectural-principles)
- [4. Architecture Decision Records (ADRs)](#4-architecture-decision-records-adrs)
   - [ADR-001 — LangGraph as the orchestration substrate](#adr-001-langgraph-as-the-orchestration-substrate)
   - [ADR-002 — LLM judgment, no unilateral action](#adr-002-llm-judgment-no-unilateral-action)
   - [ADR-003 — Two retrieval indexes by corpus type (Incident, SOP)](#adr-003-two-retrieval-indexes-by-corpus-type-incident-sop)
   - [ADR-004 — Typed resolution (`ACTION` | `SOP` | `NONE`); SOP is terminal](#adr-004-typed-resolution-action-sop-none-sop-is-terminal)
   - [ADR-005 — Config-driven governance in Postgres](#adr-005-config-driven-governance-in-postgres)
   - [ADR-006 — Retrieval-as-router: precision@1, margin, calibration](#adr-006-retrieval-as-router-precision1-margin-calibration)
   - [ADR-007 — Clarify loop with an in-loop retrieval probe](#adr-007-clarify-loop-with-an-in-loop-retrieval-probe)
   - [ADR-008 — Short-term vs long-term memory separation](#adr-008-short-term-vs-long-term-memory-separation)
   - [ADR-009 — Per-tenant tool injection (native + MCP)](#adr-009-per-tenant-tool-injection-native-mcp)
   - [ADR-010 — Approval as out-of-band suspend/resume, verdict via a single Staff API operation](#adr-010-approval-as-out-of-band-suspendresume-verdict-via-a-single-staff-api-operation)
   - [ADR-011 — Signed, idempotent execution keyed on `request_id`](#adr-011-signed-idempotent-execution-keyed-on-requestid)
   - [ADR-012 — Evaluation harness as a release gate](#adr-012-evaluation-harness-as-a-release-gate)
- [5. Technology Stack](#5-technology-stack)
- [6. The Graph](#6-the-graph)
   - [6.1 Topology](#61-topology)
   - [6.2 State Shape](#62-state-shape)
- [6.3 Execution authority boundary](#63-execution-authority-boundary)
- [7. Node Reference — Intent, Behaviour, Mechanism](#7-node-reference-intent-behaviour-mechanism)
   - [7.1 Intake & Clarify](#71-intake-clarify)
   - [7.2 Resolution Selection](#72-resolution-selection)
   - [7.3 SOP Branch (guided, terminal)](#73-sop-branch-guided-terminal)
   - [7.4 Action Branch (governed)](#74-action-branch-governed)
   - [7.5 Tail](#75-tail)
- [8. Approval Servicing Model (Staff API verdict, SignalR notification, out-of-band)](#8-approval-servicing-model-staff-api-verdict-signalr-notification-out-of-band)
   - [8.1 Two Interrupts, Two Transports](#81-two-interrupts-two-transports)
   - [8.2 Suspend/Resume, Not Blocking](#82-suspendresume-not-blocking)
   - [8.3 The Flow](#83-the-flow)
   - [8.4 Live vs Non-Live (evaluated at verdict arrival)](#84-live-vs-non-live-evaluated-at-verdict-arrival)
   - [8.5 No Timeout — Human-Only Lifecycle](#85-no-timeout-human-only-lifecycle)
   - [8.6 Correlation & Safety](#86-correlation-safety)
   - [8.7 `approval_requests` (operational state, not config)](#87-approvalrequests-operational-state-not-config)
   - [8.8 Servicing Slice](#88-servicing-slice)
- [9. Retrieval Architecture (RAG Core)](#9-retrieval-architecture-rag-core)
   - [9.1 Two Indexes, Two Chunking Strategies](#91-two-indexes-two-chunking-strategies)
   - [9.2 Field-Scoped Embedding (resolution-leakage guard)](#92-field-scoped-embedding-resolution-leakage-guard)
   - [9.3 Hybrid Is Load-Bearing](#93-hybrid-is-load-bearing)
   - [9.4 Rerank, with a Cost Knob](#94-rerank-with-a-cost-knob)
   - [9.5 Confidence, Margin, Calibration](#95-confidence-margin-calibration)
   - [9.6 Shared-Tenant `tid` Filter vs ANN Recall](#96-shared-tenant-tid-filter-vs-ann-recall)
   - [9.7 Long-Term Recall Priority](#97-long-term-recall-priority)
- [10. Evaluation & Observability](#10-evaluation-observability)
   - [10.1 Golden-Set Record (field contract)](#101-golden-set-record-field-contract)
   - [10.2 Metrics](#102-metrics)
   - [10.3 Release Gates (starting values — calibrate on your own set)](#103-release-gates-starting-values-calibrate-on-your-own-set)
   - [10.4 Process](#104-process)
- [12. Open Decisions](#12-open-decisions)
- [13. Still to Specify](#13-still-to-specify)

---


## 1. Purpose & Thesis

This document specifies the retrieval-augmented, agentic architecture for a multi-tenant self-service
ITSM resolver. A user raises a problem in natural language; the agent refines that problem, retrieves the
most similar prior incident, follows that incident's resolution — either a guided SOP or a governed
Action — and, when the resolution is an action, executes it through an approval-gated, signed, idempotent
tool call against an external API or MCP server.

The governing thesis, which shapes almost every decision below, is: **this is retrieval-as-router, not
retrieval-as-context.**

In a conventional RAG assistant, weak retrieval yields a weaker answer. Here, retrieval selects which
governed action fires. A wrong incident match loads the wrong action definition, which invokes the wrong
signed tool. Retrieval quality is therefore a **safety property**, and the optimization target is
precision@1 with calibrated confidence, not precision@k. Every design choice that follows is downstream
of that reframe.

## 2. Scope & Context

**In scope.** The LangGraph orchestration graph; the two-index Azure AI Search retrieval layer (shared-tenant, `tid`-filtered); the clarify/refinement loop; typed resolution selection; the Postgres-backed governance layer (action definitions, action↔tool bindings); the approval servicing model (SignalR, out-of-band); memory (short- and long-term); signed idempotent execution; and the evaluation harness that gates releases.

**Out of scope.** Platform topology, network boundaries, Azure deployment, APIM configuration, identity establishment, tenant onboarding, client UI, and ServiceNow platform integration are defined by the Overall Architecture, Identity Plane and Product Functional Specification. This document consumes those capabilities; it does not redefine them.

**Identity dependency — mandatory.** This document conforms to `identity-plane.md`. RagCore does not establish human identity, tenant identity, persona, approval authority or Workload authority. For human requests it consumes the trusted identity context established by the platform. For asynchronous execution it uses the tenant/requester/action/target/approval context stored on the durable work item. Untrusted model output, retrieved content, messages, realtime events and trigger payloads cannot widen or replace that authority.

## 3. Architectural Principles

**Identity contract.** All identity, tenant-binding and authority rules are inherited from `identity-plane.md`. This document never creates a competing identity or authorization model.

Standing constraints. Every ADR in Section 4 applies one or more of them.

1. **Judgment without unilateral action.** The LLM proposes; it never executes. Every side effect passes
   through policy → approval → signed execution. Enforced structurally in the graph, not by prompt
   discipline.
2. **Retrieval-as-router.** Retrieval selects governed actions, so it is measured and gated as a router:
   precision@1, calibrated confidence, score margin, safety metrics.
3. **Config over code for governance.** What is approvable and what tool an action binds to are data in
   Postgres, versioned and per-action — not branches in the graph.
4. **Two confidence axes, never conflated.** Understanding confidence (is the problem well-specified?)
   and match/grounding confidence (can the KB actually resolve it?) are separate signals with separate
   thresholds and separate consequences.
5. **Tenant isolation is a hard boundary.** Every retrieval, memory read, tool binding, and config lookup
   is scoped by `tid`. Cross-tenant leakage is a release-blocking defect, not a quality metric.
6. **Deterministic, idempotent, signed side effects.** Actions are keyed on `request_id`, signed with a
   per-tenant vendor profile, and safe to replay after an arbitrarily long approval suspension.
7. **Fail toward humans.** When confidence, coverage, or governance is unsatisfied, the agent escalates
   cleanly with full context rather than guessing.
8. **Evaluation is part of the system.** A labeled golden set and metric suite gate every change that can
   move retrieval behaviour (embeddings, chunking, prompts, thresholds).
9. **One verdict ingress, human-authored.** All approval verdicts enter through a single authenticated
   Staff API operation, submitted with a fresh staff token; SignalR notifies and delivers results but is
   never the authorization channel. There are no system-synthesized approvals and no timeouts — absent a
   human decision, an approval-required action does not proceed, and the graph remains suspended
   indefinitely. Once granted, an approval carries a bounded execution-validity window.
10. **One session, one case, one work item.** A graph thread is 1:1 with a ServiceNow case and 1:1 with
   the platform work item that holds the authority context. A work item carries **at most one approval**;
   a second approval-requiring operation in the same session escalates rather than raising a second
   approval.
11. **The graph proposes; it never holds authority.** Checkpoint state is working state. Tenant,
   requester, action, target and approval state live on the work item in PostgreSQL and are immutable
   there.

## 4. Architecture Decision Records (ADRs)

Condensed form: Context → Decision → Consequences.

### ADR-001 — LangGraph as the orchestration substrate
**Context.** The flow is stateful, branches heavily, must pause for human input mid-execution, and must
survive arbitrarily long approval suspensions.
**Decision.** Use LangGraph `StateGraph` with a durable checkpointer; model pauses with `interrupt()`;
resume with `Command`.
**Consequences.** Durable pauses and time-travel/audit for free; a suspended `interrupt()` holds no worker
or process open — it is a persisted checkpoint; requires disciplined idempotency on side-effecting nodes.

### ADR-002 — LLM judgment, no unilateral action
**Context.** Platform principle; actions are signed and operator-supervised.
**Decision.** No side-effecting tool is callable directly from the agent loop. Actionable resolutions route through `load_action_definition → prepare_action → resolve_tool_binding → (approval) → execute_action`. Only `execute_action` performs the effect, and execution occurs under the Workload principal using the authoritative durable work-item context defined by the Identity Plane.
**Consequences.** Uniform, auditable governance path; a few extra nodes; the model cannot decide to act
even if prompted to.

### ADR-003 — Two retrieval indexes by corpus type (Incident, SOP)
**Context.** Incidents are short atomic symptom→resolution records; SOPs are long procedural documents.
One index forces one chunking strategy that compromises both.
**Decision.** Two Azure AI Search indexes with independent schemas, chunking, and analyzers. Incident
retrieval is primary; SOP retrieval is conditional on a SOP-typed resolution. Both are shared-tenant,
single-index with `tid` as a mandatory filter (not index-per-tenant).
**Consequences.** Each corpus is tuned correctly; simple ingestion; clean separation of finding the
problem from rendering the procedure. Shared HNSW + selective `tid` pre-filter introduces a small-tenant
recall risk that is monitored (§9.6), not architected around.

### ADR-004 — Typed resolution (`ACTION` | `SOP` | `NONE`); SOP is terminal
**Context.** A matched incident points to a resolution that is either "here's what to do" (guided) or
"let the system do it" (governed).
**Decision.** Matched incidents carry a `resolution_ref {type, id}`. `select_resolution` emits
`resolution_type`, forking the graph: `SOP` → guided and terminal (no embedded actions); `ACTION` →
governed pipeline; `NONE`/low-confidence → escalate.
**Consequences.** The safety-critical path (`ACTION`) is isolated and short; SOP delivery stays a simple
leaf with no re-entry into governance; a type-confusion failure mode appears and is measured explicitly
(§10).

### ADR-005 — Config-driven governance in Postgres
**Context.** Approval requirements and tool wiring change per action over time; hardcoding couples
governance to deploys.
**Decision.** Two governance-config surfaces in Postgres: action definitions (enabled, risk tier,
`approval_required`, param schema) and action↔tool bindings (tool id, kind [native|MCP], endpoint,
signing profile, idempotency policy). A third, operational surface — `approval_requests` — is durable
state, not config (§8), and references the work item that carries the authority context. Retrieval/loop thresholds are global system constants, not per-tenant config.
**Consequences.** Governance changes are versioned, auditable data; the graph stays generic; config
integrity is first-class (bad config is a bad action). Global thresholds keep the loop simple and uniform
across tenants.

### ADR-006 — Retrieval-as-router: precision@1, margin, calibration
**Context.** Retrieval routes to signed actions.
**Decision.** Gate on top-1 correctness; use score margin (top1 − top2) alongside absolute score as the
confidence signal; calibrate thresholds on a labeled set. Raw similarity scores are never treated as
probabilities. Thresholds are global but still calibrated, not guessed.
**Consequences.** Near-ties route differently from confident singletons at the same top-1 score;
requires a calibration set and an ECE check per release.

### ADR-007 — Clarify loop with an in-loop retrieval probe
**Context.** A well-phrased problem can still be uncoverable by the corpus; generic questions waste
iterations.
**Decision.** A `probe_retrieval` node runs non-committing hybrid+rerank each iteration.
`assess_understanding` combines understanding and grounding signals and uses the probe's `ambiguity_type`
to choose discriminating questions. The loop exits when both axes clear their global bars, or escalates
on no-coverage / out-of-scope / max-iterations.
**Consequences.** Sharper questions, earlier fail-fast on uncoverable problems, no double retrieval (the
exit-iteration probe feeds `select_resolution`); per-iteration rerank cost is a knob (§9.4).

### ADR-008 — Short-term vs long-term memory separation
**Context.** Turn memory, cross-session recall, and their differing scopes/lifetimes.
**Decision.** Short-term = thread messages + working state via the checkpointer, keyed
`tenant:user:session`. Long-term = a `tid`-namespaced `BaseStore` (`tid`, `users`, `user_id`) holding
profile and prior incident outcomes, backed by vector search.
**Consequences.** Correct LangGraph idiom; long-term recall is advisory, ranked below the incident index,
and never overrides a match.

### ADR-009 — Per-tenant tool injection (native + MCP)
**Context.** Tenants have different entitlements; MCP servers add tools dynamically.
**Decision.** Tools resolve at request time from the tenant entitlement matrix and the Postgres binding,
merging native connectors and MCP-discovered tools. Each tool carries a sensitivity tag (read | action)
determining inline execution vs governance.
**Consequences.** Least-privilege per tenant; no global toolset; MCP tools inherit the same governance as
native ones.

### ADR-010 — Approval as out-of-band suspend/resume, verdict via a single Staff API operation
**Context.** Key actions need operator sign-off; waits can be long; the platform is event-driven;
governance wants one auditable decision point.
**Decision.** `human_approval` writes a pending record to `approval_requests`, then `interrupt()`s — the
run suspends and returns (no held worker). The **authenticated Staff API approval operation is the sole
verdict ingress**; SignalR pushes the notification to the operator console and delivers the result, but
never carries the decision. Live session → immediate `Command` resume + stream to the user; non-live →
verdict written into the checkpoint state and a background resume driver completes the graph. Execution
fires on approval regardless of user presence **for server-side execution**; an operation executed from
the desktop additionally requires the user to be present. There is no timeout and no system-synthesized
verdict; pending is indefinite. Once granted, the approval starts a bounded execution-validity window,
after which the work item expires and requires fresh authorization. Liveness is evaluated at verdict
arrival.
**Consequences.** Long human-latency waits are first-class and hold no resources; one ingress means
authz, idempotency, and audit are enforced in one place — at the API, where the staff token, role set and
tenant can be validated; the only approval transitions are pending → approved and pending → rejected,
both human-authored; stale pendings are an operational visibility concern (console queue), not a graph
edge; delivery of the execution trigger becomes a correctness concern because of the validity window.

### ADR-011 — Signed, idempotent execution keyed on `request_id`
**Context.** A resumed graph must not double-execute; external effects must be attributable.
**Decision.** `execute_action` runs under the **Workload** principal (app-only authorization, customer
tenant resolved only from the durable work item), atomically claims the work item, then calls the mapped
tool with a signed payload (per-tenant Key Vault profile) and `idempotency_key = request_id`. Where the
resolution is a predefined catalogue script run on the endpoint, the executing principal is instead the
signed-in end user via the desktop client, and `executed_by` records that.
**Consequences.** Two idempotency boundaries: the claim protects the platform against duplicate triggers,
the key protects the external system against duplicate effect. Safe replays across suspend/resume;
attributable actions; a decision remains on whether failed-then-retried actions re-fire via an attempt
sub-key (§12).

### ADR-012 — Evaluation harness as a release gate
**Context.** A router that selects actions can silently regress into selecting wrong actions.
**Decision.** Maintain a golden set of `problem_statement → correct resolution_ref` with adversarial
cases; measure relevance and safety; block releases on hard gates (§10). Re-run on any change that moves
retrieval behaviour.
**Consequences.** Regressions caught pre-ship; curation discipline required; the golden set is living
(production failures become regression cases).

## 5. Technology Stack

| Capability | Technology / mechanism | Responsibility in this document |
|---|---|---|
| Orchestration | LangGraph (`StateGraph`, `interrupt`, `Command`) | Durable graph execution and pause/resume |
| LLM access | Azure OpenAI + Anthropic via the platform AI Gateway | Model invocation; provider abstraction is platform-managed |
| Retrieval | Azure AI Search — Incident + KB indexes | Tenant-scoped hybrid retrieval |
| Reranking | Azure AI Search semantic ranker / cross-encoder | Retrieval quality and cost control |
| Short-term memory | LangGraph checkpointer | Durable graph state |
| Long-term memory | LangGraph `BaseStore` | Tenant-scoped advisory recall |
| Governance state | PostgreSQL | Action definitions, tool bindings and approval operational state |
| Tool execution | Native tools + MCP through governed bindings | Controlled side effects |
| Approval ingress | Staff API verdict operation | Sole approval verdict ingress; realtime delivery is notification |
| Signing / credentials | Platform secret/signing capability | Per-tenant vendor signing profiles |
| Evaluation | Golden set + metric/release gates | Retrieval and agent safety validation |

Hosting, networking, APIM, Container Apps, Service Bus, Key Vault deployment and other platform concerns are defined by the Overall Architecture. Identity and authority rules are defined by `identity-plane.md`.

## 6. The Graph

### 6.1 Topology

*Figure 1 — ITSM self-service resolver: full graph topology.*

The graph edges around `human_approval` are unchanged; the servicing of the interrupt (SignalR hub,
live/non-live resume) happens out-of-band and is detailed in Section 8.

### 6.2 State Shape

Short-term = checkpointer thread state; long-term = store; the rest is per-request working state.

**Identity & config** (set once, read-only after): `tid`, `user_id`, `request_id`, `work_item_id`,
`case_ref`, `config` (global constants surfaced into state). These are **copies of** trusted context, not
the source of it: tenant, requester, action, target and approval state are authoritative on the work item
in PostgreSQL, where they are immutable.

**Clarify loop** (short-term): `messages` (append), `problem_statement` (accumulates),
`understanding_confidence`, `grounding_confidence`, `score_margin`, `ambiguity_type`,
`clarify_iterations`, `pending_question`, `intent`, `urgency`, `in_scope`.

**Long-term working set:** `user_profile`, `recalled_incidents`.

**Retrieval & resolution:** `probe_candidates`, `resolution_type` {`ACTION`, `SOP`, `NONE`},
`resolution_ref {type, id}`, `match_confidence`, `sop_document`.

**Action governance:** `action_definition`, `action_params`, `params_status` {complete, missing,
unresolvable}, `tool_binding`, `execution_treatment` {AUTO, END_USER_APPROVAL, STAFF_APPROVAL,
NOT_ALLOWED}, `approval_request_id`, `approval {approved, approver_id, reason, ts}`,
`consent {granted, user_id, ts}`, `action_result`.

**Outcome:** `outcome` {answered_sop, resolved_action, escalated, denied}, `escalation_reason`.

### 6.3 Execution authority boundary

The following boundary is normative:

```text
LLM / RagCore
      │
      │ proposes intent, resolution or action parameters
      ▼
Governance / policy
      │
      │ determines whether the operation is allowed and what approval is required
      ▼
Work item
      │
      │ authoritative tenant, requester, target, action and approval state
      ▼
Approval (when required)
      │
      │ authenticated Staff API verdict
      ▼
Workload
      │
      │ executes as the non-human principal defined by Identity Plane
      ▼
Adapter / Tool
      │
      ▼
External system
```

**The LLM never owns execution authority.** It cannot choose or change the authoritative tenant, requester, target, approval state, credential profile or execution identity. The Workload is the execution actor; the originating human remains recorded as provenance (`requested_by_oid` / `on_behalf_of_oid`).

**No side effect may occur directly from an agent node.** Only the governed execution path may perform a consequential operation. Before execution, the Workload must re-read the durable work item and verify tenant, action, target, approval and execution-validity state. The Workload must not accept these authority-bearing values from trigger payloads, chat text, retrieved documents, SignalR messages or model output.

**Identity reference.** The exact principal, tenant-binding and authority rules are defined in `identity-plane.md`; this section defines how RagCore respects that authority boundary.

## 7. Node Reference — Intent, Behaviour, Mechanism

For each node: **Intent** (why it exists), **Should do** (its contract), **How** (mechanism).

### 7.1 Intake & Clarify

**`load_context`** — Intent: establish identity and prime memory. Should do: set `request_id`; surface
global config constants; hydrate `user_profile`, `recalled_incidents`; init `clarify_iterations = 0`. How:
read the `tid`-namespaced store; generate/accept the idempotency key.

**`intake_problem`** — Intent: seed the working problem and anchor the session. Should do: write
`problem_statement` from the first user turn; commit the ServiceNow case and bind `case_ref` and
`work_item_id`. How: copy from `messages`; case creation is an `AUTO`-classified catalogue operation
performed through the ServiceNow adapter. One session, one case, one work item.

**`probe_retrieval`** (non-committing) — Intent: measure corpus coverage and expose ambiguity shape.
Should do: write `probe_candidates`, `grounding_confidence` (norm. top-1 rerank), `score_margin`
(top1 − top2), `ambiguity_type` {none, symptom_underspecified, competing_resolutions, type_conflict};
commit nothing. How: Azure AI Search incident index, `tid`-filtered hybrid + rerank on
`problem_statement`.

**`assess_understanding`** (loop hub) — Intent: decide readiness on two axes; when not ready, ask the
single most informative question. Should do: write `understanding_confidence`, `in_scope`, and on the
passing turn `intent` + `urgency`; increment `clarify_iterations`; when not ready write
`pending_question` chosen against `ambiguity_type`. How: one LLM scoring call over `problem_statement` +
`messages` + probe signal; global thresholds. Routing: ready (U ≥ U_thr AND G ≥ G_thr AND
margin ≥ margin_floor) → `select_resolution`; no_coverage → `vendor_guidance` when the request is a
genuine IT question inside the configured permitted areas, otherwise escalate; out_of_scope or
iter ≥ max → escalate; else → `ask_user`.

**`ask_user`** (interrupt · console) — Intent: obtain the end user's clarifying answer without losing
loop state. Should do: fold the answer into `problem_statement` and `messages`. How: `interrupt(pending_question)`
in the user's own chat console; the run suspends indefinitely until the user answers (no third party, no
SignalR); unconditional edge back to `probe_retrieval`.

### 7.2 Resolution Selection

**`select_resolution`** (committing) — Intent: commit a resolution and compute the act-authorizing gate.
Should do: write `resolution_type`, `resolution_ref`, calibrated `match_confidence` (with margin). How:
consume the exit-iteration `probe_candidates` (no re-retrieval); LLM grounds/ranks; calibrated scoring.
Routing: SOP → `retrieve_sop`; ACTION → `load_action_definition`; NONE or
`match_confidence < match_threshold` → escalate.

### 7.3 SOP Branch (guided, terminal)

**`retrieve_sop`** — Intent: fetch the referenced procedure. Should do: write `sop_document`. How: Azure
AI Search SOP index, `tid`-filtered, by `resolution_ref.id`.

**`present_sop`** — Intent: deliver grounded step-by-step guidance; terminal. Should do: append assistant
message; set `outcome = answered_sop`. How: LLM renders the SOP against the problem; faithfulness-checked
(§10). No re-entry into governance — SOPs carry no embedded actions.

**`vendor_guidance`** (terminal) — Intent: answer a genuine IT question the corpus cannot cover. Should
do: append grounded guidance with the mandatory disclaimer; set `outcome = answered_external`. How: fetch
from an allow-listed vendor documentation source within the configured permitted areas; fetched content
is **untrusted data**, passed through inbound and outbound content safety and never treated as
instruction. No approval required; no execution — anything actionable re-enters the governed branch.

### 7.4 Action Branch (governed)

**`load_action_definition`** — Intent: load the governance contract. Should do: write
`action_definition` (enabled, risk tier, `approval_required`, param schema). How: Postgres read by
`resolution_ref.id`, `tid`-scoped. Routing: enabled & valid → `prepare_action`; else → escalate
(`action_disabled`).

**`prepare_action`** (may interrupt · console) — Intent: assemble and validate parameters. Should do:
write `action_params`, `params_status`. How: bind from incident/conversation/profile against schema; if
required params missing, `interrupt()` the user (console) and fold the answer in. Routing: complete →
`resolve_tool_binding`; unresolvable → escalate.

**`resolve_tool_binding`** — Intent: determine how execution happens and whether sign-off is needed.
Should do: write `tool_binding` (tool id, kind, endpoint, signing profile, idempotency policy) and
`execution_treatment`. How: Postgres action↔tool mapping; enforce tenant entitlement; the treatment comes
from the catalogue entry for the resolved action, never from the model. Routing: `STAFF_APPROVAL` →
`human_approval`; `END_USER_APPROVAL` → `await_consent`; `AUTO` → `record_policy_decision`;
`NOT_ALLOWED` → escalate (`policy_blocked`).

**`human_approval`** (interrupt · SignalR out-of-band — see Section 8) — Intent: obtain operator
sign-off. Should do: write a pending row to `approval_requests` (correlation keys), write
`approval_request_id` to state, then `interrupt()` so the run suspends and returns. On resume, write
`approval {approved, approver_id, reason, ts}`. How: the verdict arrives only through the authenticated
Staff API approval operation, validated against the approver's role set and the pending row's `tid`;
SignalR delivers the notification and the result. The approval request discloses every individual command
the operation will run, with its plain-language description, plus the script catalogue id and version
where applicable. Live → immediate resume, non-live → verdict materialized into the checkpoint by the
background driver. No timeout; pending is indefinite, but the granted approval starts the
execution-validity window. Routing: approved → `execute_action`; rejected → escalate
(`approval_rejected`).

**`await_consent`** (interrupt · console) — Intent: obtain the end user's authorization for a self-scoped
operation. Should do: write `consent {granted, user_id, ts}`. How: the prompt is rendered in the user's
chat, but the decision arrives as an authenticated Customer API call bound to the work item and made by
the work item's requester; a free-text "yes" in the transcript is never the authority. Routing: granted →
`execute_action`; refused → close (`consent_refused`).

**`record_policy_decision`** — Intent: uniform audit for `AUTO` operations. Should do: write the policy
decision and its reasons. How: stamp only; no suspension. **No approval record is created and
`approved_by` remains null** — `approved_by` always means a human approved.

**`execute_action`** — Intent: perform the one authorized side effect. Should do: write `action_result`;
set `outcome = resolved_action`. How: re-read the work item and verify it is authorized, the tenant is
active, it is not cancelled and the validity window has not expired; atomically claim it; then invoke the
mapped tool — external API / MCP — under the Workload principal with a signed payload (Key Vault) and
`idempotency_key = request_id`. Where the resolution is a predefined catalogue script, the desktop client
executes it under the signed-in user's authority against an instruction fetched over the authenticated
Customer API, and posts the result back the same way. Routing: success → `verify` then `respond`; failure
→ escalate (`execution_failed`). Failed side effects are **not** retried automatically.

### 7.5 Tail

**`escalate`** — Intent: clean human hand-off with full context. Should do: set `outcome = escalated`;
append notice; record `escalation_reason`. How: update the session's existing ServiceNow case — committed
at `intake_problem` — with transcript, probe candidates and reason, and route it to the technician queue.

**`respond`** — Intent: final user-facing message. Should do: emit closing message if not already
produced by `present_sop`/`escalate`. How: pass-through or short LLM summary.

**`write_memory`** — Intent: feed future matching/recall. Should do: persist an outcome record; no
thread-state write. How: store put to `(tid, users, user_id)` keyed by `request_id` (idempotent).

## 8. Approval Servicing Model (Staff API verdict, SignalR notification, out-of-band)

Two graph interrupt points serve fundamentally different roles and must not be treated as one mechanism.

### 8.1 Two Interrupts, Two Transports

- **`ask_user` → console, always.** The end user answers a clarifying question inside their own chat; it
  resumes as an ordinary conversational turn. No operator, no SignalR. If the user walks away, the graph
  stays suspended at the checkpoint and resumes whenever they return. There is no non-live variant: only
  the user can answer their own question.
- **`human_approval` → Staff API, always the ingress.** An authorised staff member decides. The verdict
  enters through exactly one door — an authenticated Staff API operation carrying a fresh staff token — in
  both live and non-live cases, so authz (approver's role set vs action governance + the pending row's
  `tid`), idempotency (first valid verdict wins), and audit are all enforced at one point. SignalR pushes
  the notification and the result; it is a delivery mechanism, never an authorization mechanism.
- **`await_consent` → Customer API, always the ingress.** The affected end user authorizes a self-scoped
  operation. The prompt appears in their chat; the decision is an authenticated API call bound to the
  work item.

### 8.2 Suspend/Resume, Not Blocking

`human_approval` calling `interrupt()` on a durably-checkpointed graph does not hold a worker or process —
it persists a checkpoint and returns. Blocking would only mean the original HTTP invocation waiting;
moving the resume to an event handler makes the same `interrupt()` fully out-of-band. The topology is
unchanged; only the servicing around it changes.

### 8.3 The Flow

1. `resolve_tool_binding` routes an approval-required action to `human_approval`.
2. `human_approval` writes a pending row to `approval_requests` (keyed by `request_id` + `thread_id` +
   `checkpoint_id` + `tid` + `action_id`), then `interrupt()`s — the run suspends and returns.
3. A publisher pushes the request to the operator console over SignalR, and the request is persisted so
   an offline approver sees it on next sign-in.
4. The staff member decides; the verdict posts back through the authenticated Staff API approval
   operation with a fresh staff token.
5. The Approval service validates against the pending row (correlation + idempotency + approver role set
   + `tid`) and flips pending → decided in one transaction, setting the execution-validity window.
6. Resume is servicing-mode-dependent (§8.4), continuing the exact graph from `human_approval` into
   `execute_action` (approve) or `escalate` (reject).

### 8.4 Live vs Non-Live (evaluated at verdict arrival)

- **Live** — user session active when the verdict lands. Staff API → immediate
  `invoke(Command(resume=verdict))` → graph continues → result streams to the connected user.
- **Non-live** — user gone/dormant. Staff API → verdict written into the LangGraph checkpoint state, and
  a background resume driver drives the graph to completion; the outcome is persisted and delivered on
  the user's return or via notification. This holds for server-side execution. A resolution that must be
  executed from the desktop cannot complete while the user is absent and expires with the validity
  window.

A user live at request time but gone at verdict time is treated as non-live — liveness is judged when the
verdict arrives, not when the request was raised. Critically, execution fires on approval regardless of
user presence: approval authorizes a signed side effect, so non-live still runs `execute_action` to
completion. Live/non-live differs in delivery (stream vs persist), never in whether execution happens.

### 8.5 No Timeout — Human-Only Lifecycle

This is a human-in-the-loop flow: unless an operator acts, nothing changes. There is no timer, no
auto-reject, no `system:timeout` verdict. A pending approval — and the suspended graph behind it —
persists indefinitely. On the **pending** row `expires_at`, if kept, is advisory staleness metadata for
reporting only; it triggers nothing. This is distinct from the work item's post-approval
execution-validity window, which is enforced and does expire the authorization. The safety net is visibility, not automation: the operator console rehydrates the full
pending queue from `approval_requests` (the source of truth), surfacing aging items — a UI cue with no
state change. Any SLA concern is a dashboard alert, not a graph edge. The approval lifecycle therefore has
exactly two transitions, both human-authored: pending → approved and pending → rejected.

### 8.6 Correlation & Safety

- **Correlation key** — `request_id` (+ `thread_id`, `checkpoint_id`) carried in the SignalR payload and
  echoed by the verdict; this is how a verdict finds its suspended graph.
- **Idempotent decide** — duplicate/retry/double-click verdicts all hit the one pending → decided
  transaction; first valid wins, the rest are no-ops.
- **Reconnect resilience** — SignalR delivery is best-effort; Postgres `approval_requests` is the source
  of truth. On operator reconnect the console rehydrates pending items from Postgres, not from missed
  socket messages.
- **AuthZ at the API** — validate the approver's role set against the action's governance and the pending
  row's `tid` at the Staff API operation, not in the console UI and not at the socket.

### 8.7 `approval_requests` (operational state, not config)

Columns: `request_id`, `thread_id`, `checkpoint_id`, `work_item_id`, `tid`, `action_id`, `status`
{pending, approved, rejected}, `decided_by` (Entra `oid`), `decided_at`, `verdict`, `reason`, optional
`expires_at` (advisory staleness), `created_at`. Distinct from the governance config tables in Section 4 / ADR-005.

### 8.8 Servicing Slice

*Figure 2 — Approval servicing: out-of-band suspend/resume. Verdict enters over the Staff API; SignalR
notifies and delivers results. No timeout path exists on the pending state.*

## 9. Retrieval Architecture (RAG Core)

Because retrieval routes to governed actions, the retrieval layer is engineered as a router — precision@1
and safety, not precision@k relevance alone.

### 9.1 Two Indexes, Two Chunking Strategies

Incidents are short atomic records — indexed at record granularity (symptom + `resolution_ref` +
metadata), no windowed chunking. SOPs are long procedures — semantic/section chunking with overlap tuned
on real SOP documents (never a blind 512). The two never share a schema or analyzer.

### 9.2 Field-Scoped Embedding (resolution-leakage guard)

Embed the symptom/description field for the query-time match; carry `resolution_ref` and resolution text
as payload metadata, not embedded content. Embedding the whole record matches partly on how it was
fixed, collapsing incidents that share a fix but differ in symptom — the exact failure a router must
avoid.

### 9.3 Hybrid Is Load-Bearing

ITSM text is saturated with exact-match tokens — error codes (`0x8007000E`), CI names, KB numbers,
hostnames, SKUs. Dense vectors blur these; BM25 recovers them. The sparse leg is weighted, not decorative,
and the test suite includes identifier-dominated queries.

### 9.4 Rerank, with a Cost Knob

Rerank the top-k before committing. Because the probe reruns every clarify iteration, gate the reranker:
rerank a small top-k only, or run cheap hybrid each iteration and invoke the reranker only above a minimum
dense/sparse floor. Topology-neutral cost/latency lever.

### 9.5 Confidence, Margin, Calibration

Never threshold a raw similarity score as a probability. The act/escalate gate uses absolute score +
margin (top1 − top2), with thresholds calibrated on a labeled set and an ECE check per release. Thresholds
are global constants but still calibrated, not guessed.

### 9.6 Shared-Tenant `tid` Filter vs ANN Recall

Single Incident and single SOP index, `tid` a mandatory and non-bypassable filter — the isolation
boundary. There is no cross-tenant grounding corpus; a dedicated per-tenant index is used only to pin
residency, never as the isolation mechanism. On a shared HNSW
graph a highly selective `tid` pre-filter can degrade recall for small tenants (the graph was built over
all tenants' vectors). This is monitored: load-test with the smallest tenant, not the average; watch
small-tenant recall over time. `cross_tenant_leakage_rate == 0` stays the hard release gate.

### 9.7 Long-Term Recall Priority

`recalled_incidents` from the store is advisory: it may sharpen clarifying questions but ranks below the
incident index and never overrides a match. A user's stale prior incident must not bias the current
diagnosis.

## 10. Evaluation & Observability

Because retrieval routes to governed actions, the harness measures a router.

### 10.1 Golden-Set Record (field contract)

`case_id`, `tid`, provenance; `raw_problem_statement`; `scripted_answers` (deterministic replay of the
clarify loop); labels `expected_in_scope`, `expected_resolution_type` (ACTION|SOP|ESCALATE),
`expected_resolution_ref`, `expected_action_id`, `expected_approval_required`,
`acceptable_alternatives`; tags/difficulty.

Mandatory adversarial cases: out-of-corpus (→ escalate via no_coverage), cross-tenant bait (→ NONE here),
type-confusable pairs, near-tie pairs (exercise the margin gate and the disambiguation question).

### 10.2 Metrics

| Group | Metric | Meaning |
|---|---|---|
| Relevance | precision@1, MRR | Top-1 correctness; how far off misses are |
| Safety | `wrong_action_selection_rate` | Committed ACTION ref ≠ expected — segment by risk tier |
| Safety | `type_confusion_rate` | ACTION↔SOP mispredictions |
| Safety | `cross_tenant_leakage_rate` | Any nonzero = isolation breach |
| Safety | `false_act_rate` | Acted when the case should have escalated |
| Calibration | `match_confidence` ECE + reliability curve | Does 0.9 mean ~90%? |
| Calibration | `escalation_precision` | Genuine un-resolvables vs. catchable retrieval misses |
| Loop | `clarify_efficiency` | Iterations to ready; over-/under-asking |
| SOP leg | ragas `context_precision`, `context_recall`, `faithfulness` | Grounding quality of `present_sop` |

### 10.3 Release Gates (starting values — calibrate on your own set)

- `cross_tenant_leakage_rate == 0` — hard fail otherwise
- `wrong_action_selection_rate` ≤ 1% aggregate; high-risk tier ≤ 0.1% (or approval-forced regardless of
  confidence)
- `type_confusion_rate` ≤ 2%
- precision@1 ≥ 0.85
- `false_act_rate` ≤ risk appetite
- SOP: faithfulness ≥ 0.9, `context_precision` ≥ 0.7, `context_recall` ≥ 0.6
- `match_confidence` ECE ≤ 0.05

### 10.4 Process

Segment every safety metric by risk tier. Re-run the full harness on any embedding swap, re-chunk, prompt
change, or threshold change. Treat the golden set as living — every production wrong-action or
bad-escalate becomes a regression case, staged through the Durable Functions pipeline.

## 12. Open Decisions

1. **Retry semantics of `request_id`.** The key guarantees no double-execute across resumes — but it also
   blocks a legitimate retry after execution failure. If failed actions should re-fire, `execute_action`
   needs an attempt sub-key baked into the signing profile.

## 13. Still to Specify

- Staff API verdict operation contract — correlation on `request_id`/`thread_id`/`checkpoint_id`/
  `work_item_id`, idempotent decide transaction, approver authz against action governance + `tid`.
- Desktop script execution mechanics — catalogue distribution and integrity verification on the endpoint,
  whether a catalogue entry may run elevated, and how far a client-reported result is trusted by
  `verify`.
- Background resume driver — trigger, at-least-once semantics, and how it reconciles with the checkpoint
  for non-live resumes.
- Interrupt/resume payload contracts for the two user-facing pauses (`ask_user`, `prepare_action`) and the
  operator pause (`human_approval`).
- Operator console pending-queue view — rehydration from `approval_requests`, staleness surfacing
  (advisory only).

---

*Synoptek — Confidential. Source: `RagAgent-Architecture.pdf` v1.1.*
