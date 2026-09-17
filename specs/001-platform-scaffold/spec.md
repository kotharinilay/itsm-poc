# Feature Specification: Synthia Platform Engineering Scaffold

**Feature Directory**: `specs/001-platform-scaffold`

**Feature Branch**: `scaffold/synthia-platform`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Create the Synthia platform specification for the initial engineering scaffold — autonomous ITSM agent, twelve predefined use cases as placeholders, manual fallback, three client surfaces, Entra identity, independent staff roles, deterministic governance, durable interruption and resume."

## Overview

Synthia is an autonomous IT service management agent operated by Synoptek for multiple customer
organisations from one platform. It resolves customer support requests end to end where it can do so
safely, and diagnoses, informs and assists a human technician the rest of the time.

This specification defines the **initial engineering scaffold**: a real, working platform skeleton
that proves the load-bearing *infrastructure* of the platform end to end, while containing **no
resolved use cases**. The twelve use cases of the initial product release are represented as
placeholders UC-01 through UC-12 and are awaiting product definition. Until they are defined, every
request falls back to manual resolution.

**What the scaffold proves is architecture, not product workflow.** It demonstrates that the
representative API, persistence, messaging, notification and service-to-service paths work and are
authenticated securely — through inert sample flows (FR-DEMO-001 onward). It does **not** implement
business approval semantics, and it does not need to: an approval workflow exercised against a
fixture proves that the fixture was wired up, not that the platform underneath it is sound.

**The scaffold has three application deployables** (`Synthia-Platform-Specification.md` §21.6,
ADR-0007):

| # | Deployable | Owns |
|---|---|---|
| 1 | **Platform read API** | The read side. Query, listing, dashboard and reporting over published views. **Read-only** |
| 2 | **RagCore** | Conversation, orchestration, reasoning, governance, approval, the authority record and the atomic claim. **Reaches no external system** |
| 3 | **Integrations Service** | The tool catalogue, the connector registry, and **all** traffic to external systems (FR-INTEG-001 onward) |

They meet only through the API gateway, the message transport and the durable store. **No deployable
reaches another directly** (FR-DEMO-004a).

**Why build the skeleton before the use cases**: the risky parts of this product are not the use
cases — they are identity, organisation isolation, deterministic authorization, the integrity of the
durable store, and honest reporting of what actually happened. Those must be proven first, because
every use case is built on top of them and none of them can be retrofitted safely.

**Two kinds of requirement live in this document, and the distinction is load-bearing.** Most
requirements describe the **platform**: what Synthia must do once it carries product. A smaller group
— `FR-DEMO-*` — describes the **scaffold**: what must be demonstrably working now, before any use
case exists. Deferring a demonstration is not deferring a requirement. The governance architecture,
the four execution treatments, durable suspension and the approval and consent models all remain
fully specified here and are unchanged; what has moved is only the point at which each is *exercised*
in running code.

## Clarifications

### Session 2026-09-15

- Q: What accessibility conformance level must the three client surfaces meet? → A: WCAG 2.2 Level AA
  across all three surfaces — customer portal, customer desktop and staff portal.
- Q: What language support must the scaffold provide for the user interface and for the agent's
  replies? → A: English only throughout, strings hardcoded. Externalizing strings for later
  translation is deferred, not adopted now.
- Q: What default retention should apply to chat content and to audit records? → A: Class-based
  defaults, overridable per organisation — chat content 90 days, audit 7 years, agent working state
  30 days.
- Q: Must the platform support pinning an organisation's data to a specific geographic region? → A: No
  residency support; a single region serves all organisations. Recording a region per organisation is
  deferred, not adopted now.
- Q: What operations should exist in the governance catalogue so the approval, consent and governance
  paths can actually be exercised? → A: A small set of inert reference operations, one per execution
  treatment, clearly marked as scaffold fixtures, producing no real external effect and excluded from
  production configuration.

### Session 2026-09-16 — scaffold scope correction

- Q: Must the scaffold implement working approval and consent workflows in order to be considered
  complete? → A: No. The scaffold proves **platform infrastructure**, not product workflow. It is
  complete when the representative customer, staff and workload API paths, the service-to-service
  path, PostgreSQL persistence, the transactional outbox, Service Bus publish/consume, SignalR
  notification, correlation and tenant propagation, managed-identity authentication, Key Vault secret
  binding and OpenAPI contract emission are demonstrably working and authenticated securely.
- Q: Does deferring the approval and consent demonstration remove the execution-treatment model from
  the architecture? → A: No. The four treatments, the control gate, durable suspension and the
  approval and consent authority models remain specified in full and are unchanged. Only the point at
  which they are exercised in running code has moved.
- Q: What must the sample flows act upon? → A: Inert, non-production reference operations only. A
  sample flow MUST NOT implement, stand in for, or be counted as any of UC-01 through UC-12, and MUST
  NOT produce a real effect in any external system.
- Q: What is explicitly not built in the scaffold as a result? → A: `STAFF_APPROVAL` and
  `END_USER_APPROVAL` workflow behaviour, the approval user interface, the consent user interface,
  real endpoint execution and desktop script execution.
- Q: What does the required service-to-service flow demonstrate, given that the two deployables meet
  only at the durable store and the message transport? → A: Service-to-service takes more than one
  form, and **none of them is a direct call**. Asynchronously, services meet at the message transport
  and the published views. Synchronously, a service reaches another through the **workload audience**.
  In every case the call routes **through the API gateway** — a service MUST NOT reach another
  service directly, bypassing the gateway.
  - *Count superseded 2026-09-18: there are now **three** deployables. The answer itself is unchanged
    and applies to every pair — the RagCore → Integrations Service path is its newest instance.*
- Q: Must the sample flows be exercised through a deployed public edge and gateway, or may they be
  driven against the deployables with the edge verified separately? → A: Through the **real deployed
  path**. Every sample flow is driven end to end through the public edge, the web application
  firewall, the API gateway and the container platform in a deployed environment. Configuration
  review does not substitute for traversal.

### Session 2026-09-18 — the Integrations Service boundary

Reconciling this specification with `Synthia-Platform-Specification.md` §21.6 and ADR-0007, which
make Integrations a separately deployed service parallel to RagCore. **The scaffold now has three
deployables.** No architecture is decided here; these answers decide only how the scaffold *proves*
the boundary the architecture defines.

- Q: How should the scaffold prove that RagCore cannot reach an external connector and holds no
  connector secrets, given that no sample flow may touch a real external system? → A: By **attempting
  the bypass and observing it fail**, not by asserting an absence. An inert reference connector is
  reachable only from the Integrations Service; RagCore's attempt to reach it fails at the network
  layer and its attempt to resolve a connector secret fails at Key Vault; an architecture test
  asserts no adapter, connector or provider client remains in RagCore. This mirrors the shape
  `FR-DEMO-004a` already uses for the no-direct-route rule.
- Q: What should the scaffold's synchronous ServiceNow path run against? → A: **The same inert
  reference connector**, serving an inert case-like operation. The scaffold proves the seam, not the
  vendor contract; adapter-versus-fake fidelity stays with the adapter tests, and nothing stubs a
  success and presents it as a real case.
- Q: Which idempotency boundaries must the scaffold prove now that the command crosses a deployment
  boundary? → A: **Both, proven independently.** A duplicate resume trigger absorbed by the atomic
  claim in RagCore, and a redelivered command absorbed by the derived key in the Integrations
  Service — each test failing if its own boundary alone is removed. A single end-to-end duplicate
  test would stay green on the day one of the two silently stopped working.
- Q: When a Service Bus command arrives carrying a tenant field it is not allowed to carry, what
  should the Integrations Service do? → A: **Both refuse and derive.** Boundary validation refuses
  the out-of-contract message and dead-letters it with an alert; separately, the effect is proven
  bound to the organisation on the durable record even when a conflicting one is asserted. Refusal
  proves the payload contract is closed; the binding proves where the organisation actually came
  from.
- Q: What must "the Integrations Service emits its own observable telemetry" concretely require? →
  A: The service appears as a **distinct source** in traces and logs while one correlation identifier
  still spans the journey, **and** it emits its own connector-invocation metrics — attempts,
  outcomes, duration — **and** its execution records are queryable without reference to RagCore. A
  separate telemetry workspace is explicitly not adopted; it would make the correlation identifier
  harder to follow across the seam.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An end user gets a grounded answer or an honest handoff (Priority: P1)

An employee at a customer organisation signs in on a client surface, describes an IT problem in their
own words, and receives a progressively streamed response. Where the platform can ground an answer in
approved knowledge, it answers. Where it cannot — which, until UC-01 through UC-12 are defined, is
every request that needs an action — it says so plainly and hands the request to a human, leaving a
record a technician can pick up.

**Why this priority**: This is the minimum viable slice. It proves identity, organisation scoping, session
creation, conversation, streaming, the scope guardrail and the manual fallback in one journey. Without
it nothing else can be demonstrated. It is also, on its own, useful: an honest triage-and-handoff
assistant has value even before any use case resolves automatically.

**Independent Test**: Sign in as an end user, describe a problem, observe a streamed response, and
confirm that an unsupported request produces an explicit handoff with a durable record rather than a
guess or a silent failure.

**Acceptance Scenarios**:

1. **Given** an authenticated end user on a client surface, **When** they start a chat session and
   describe an IT problem, **Then** a chat session is created, bound to their organisation, and a response
   streams back progressively.
2. **Given** a request that matches no defined use case, **When** the agent has exhausted what it can
   do, **Then** the request is escalated for human resolution, the user is told plainly that a human
   will take it, and a durable record carries the context forward.
3. **Given** a greeting or small talk, **When** the user has not yet articulated a genuine problem,
   **Then** no work record is committed.
4. **Given** a request outside IT service management, **When** the user submits it, **Then** the
   platform declines and steers the conversation back to its service function.
5. **Given** an IT question with no organisational answer, **When** the agent cannot ground it
   internally, **Then** it is treated as in scope and routed to the vendor-documentation fallback
   rather than declined.
6. **Given** a completed agent response, **When** the user records a positive or negative signal
   against that message, **Then** it is stored against that message and that user, and revising it
   replaces the previous signal rather than adding a second one.

---

### User Story 2 - A consequential action waits for a human and survives the wait (Priority: P2)

The agent proposes an operation that deterministic governance classifies as requiring staff approval.
The work suspends durably. A technician sees it in the staff portal, reviews what is proposed, and
approves or rejects it through an authenticated action. The work then resumes and executes — even if
the requesting user has closed their client, gone home, or lost access in the meantime.

**Why this priority**: This is the heart of the product and the reason the architecture exists.
"Agentic, but a human is accountable" is only real if the suspension is durable, the decision is
authenticated, and approved work survives the requester's absence.

> **Scaffold scope**: this story describes **platform behaviour and is not scaffold acceptance**
> (Clarifications, Session 2026-09-16). The scaffold does not implement `STAFF_APPROVAL` workflow
> behaviour or an approval user interface. Everything the story requires — the treatment model, the
> control gate, durable suspension, first-valid-verdict-wins, the fifteen-minute window, the actor
> chain — remains specified in full and unchanged below. What is deferred is the demonstration, not
> the design.

**Independent Test**: Using the staff-approval reference operation, drive a session to the interrupt,
close the end user's client entirely, approve from the staff portal, and confirm the work resumes and
completes without the end user present.

**Acceptance Scenarios**:

1. **Given** an operation classified as requiring staff approval, **When** the agent proposes it,
   **Then** the work suspends durably and an approval request appears in the staff queue disclosing
   every command the operation would run.
2. **Given** a suspended approval, **When** the end user's client is closed or disconnected, **Then**
   the suspended work is unaffected and remains awaiting decision.
3. **Given** a pending approval, **When** a staff member holding `technician` approves through an
   authenticated action, **Then** the decision is recorded against their identity and the work becomes
   executable for a bounded validity window.
4. **Given** an approved operation, **When** the validity window elapses without execution, **Then**
   the work becomes non-executable and requires fresh authorization; this is not reported as an error.
5. **Given** an approved operation that was never executed, **When** its window expires, **Then** it
   surfaces to humans as approved-but-not-executed rather than expiring silently.
6. **Given** an executed operation that failed, **When** the failure is recorded, **Then** it does not
   automatically retry and requires fresh human authorization.
7. **Given** a staff member holding only `administrator`, **When** they attempt to approve, **Then**
   the approval is denied.

---

### User Story 3 - An action on the user's own account or device waits for their consent (Priority: P3)

The agent proposes an operation affecting the requesting user's own account or device. The user is
shown exactly what will happen and agrees through an explicit authenticated action, not by typing
"yes" in the chat. The work then continues.

**Why this priority**: Consent is a distinct gate from approval, with a different decider and a
different authority. It must be proven separately, because collapsing the two is a security failure
that would not be visible from the approval path alone.

> **Scaffold scope**: this story describes **platform behaviour and is not scaffold acceptance**
> (Clarifications, Session 2026-09-16). The scaffold does not implement `END_USER_APPROVAL` workflow
> behaviour or a consent user interface. The requirement that consent is a distinct authority, never
> inferred from chat text, and never a substitute for staff approval, remains specified in full and
> unchanged below.

**Independent Test**: Using the end-user-approval reference operation, drive a session to the consent
interrupt, type an affirmative message in the chat, confirm nothing happens, then submit the explicit
consent action and confirm the work resumes.

**Acceptance Scenarios**:

1. **Given** an operation affecting the user's own account or device, **When** the agent proposes it,
   **Then** the work suspends and a consent prompt is rendered in the conversation.
2. **Given** a pending consent prompt, **When** the user types an affirmative message in the chat,
   **Then** no authority is conferred and the work remains suspended.
3. **Given** a pending consent prompt, **When** the user submits the explicit consent action, **Then**
   the decision is recorded against their identity and the work continues.
4. **Given** a consent submitted by someone who is not the work's requester, **When** it is received,
   **Then** it is rejected.
5. **Given** an operation classified as requiring staff approval, **When** the end user consents,
   **Then** consent does not satisfy the requirement and staff approval is still required.

---

### User Story 4 - The agent asks for clarification and continues (Priority: P4)

The agent cannot proceed without information only the user has. It asks, the session suspends, and
when the user answers, the conversation resumes from where it stopped rather than restarting.

**Why this priority**: The lightest of the three interruption types and the most common in normal use.
It shares the suspend-and-resume mechanism with the other two, so proving it also exercises the
durable-state path without involving authorization.

**Independent Test**: Drive a session to a clarifying question, leave and return to the session, answer
it, and confirm the conversation continues with its prior context intact.

**Acceptance Scenarios**:

1. **Given** insufficient information to proceed, **When** the agent needs input only the user has,
   **Then** it asks a clarifying question and the session suspends durably.
2. **Given** a suspended clarification, **When** the user returns later and answers, **Then** the
   session resumes with its prior context and continues streaming.
3. **Given** a clarifying question, **When** anyone other than the end user attempts to answer it,
   **Then** the answer is not accepted.

---

### User Story 5 - Staff work the queue with independent role capabilities (Priority: P5)

A Synoptek staff member signs in to the staff portal and sees only the modules their assigned roles
grant. They review live sessions, work the approval queue, and can take over a conversation from the
agent. What they can do is determined by which capabilities they hold, never by seniority.

**Why this priority**: Staff authorization is the area where a subtle mistake is most costly and least
visible. It must be demonstrable independently of any single approval journey.

**Independent Test**: Assign each role and each combination, then confirm module visibility and
permitted operations match the intersection of held roles and accepted roles exactly, with no implied
privilege.

**Acceptance Scenarios**:

1. **Given** a staff member holding `technician`, **When** they sign in, **Then** they see the live
   session and approval queue module.
2. **Given** a staff member holding `administrator`, **When** they sign in, **Then** they see the
   administration module and cannot approve.
3. **Given** a staff member holding both `technician` and `administrator`, **When** they sign in,
   **Then** they see both modules, because capabilities combine by union and neither implies the other.
4. **Given** an operation that accepts a role the staff member does not hold, **When** they attempt it,
   **Then** it is denied on an empty intersection.
5. **Given** a staff member acting on a customer's session, **When** they operate, **Then** the organisation
   is taken from the session and never from anything the staff member supplies.
6. **Given** an active end-user session, **When** a technician takes it over from the staff portal,
   **Then** the agent stops proposing and the technician becomes an additional sender in that
   conversation, with the handover recorded and the end user shown that a person has joined.
7. **Given** the staff portal, **When** a staff member looks for a way to start their own chat session
   or raise their own request, **Then** no such facility exists on that surface.
8. **Given** a Synoptek staff member holding `technician` and `administrator`, **When** they sign in to
   a customer surface, **Then** they are treated as an end user with end-user permissions only, their
   staff roles confer nothing, and no staff role check is applied.

---

### User Story 6 - The platform proves its own plumbing before it carries any product (Priority: P1)

An engineer deploys the scaffold and exercises a representative flow on each public audience —
customer, staff and workload — plus service-to-service calls **among the three deployables**. Each
flow acts only on an inert reference operation. Between them the flows write to and read from the
authoritative store, commit a message to the transactional outbox in the same transaction as the
state change, publish and consume that message through the queue, deliver a notification to the
originating client, **execute an inert capability through the Integrations Service and return its
result**, and carry one correlation identifier and one organisation binding from the public edge all
the way through. Every hop authenticates as itself; no secret appears in source or configuration;
**no connector credential is reachable from RagCore**; the API contract is emitted from the running
services rather than hand-written.

**Why this priority**: This is what the scaffold is *for*. The risky parts of the platform are the
seams — the transaction boundary between a state change and the message announcing it, the identity
of a service calling another service, the organisation binding surviving an asynchronous hop, the
secret that turns out to have been in a config file. None of those is exercised by a product
workflow; all of them are exercised by a flow that does nothing at all. A demonstration built on an
approval workflow proves that the fixture was wired up. A demonstration built on inert flows proves
the platform.

**Independent Test**: Can be validated by running each flow against a deployed environment and
confirming the observable outcome of each, with every hop authenticated and no real effect occurring
in any external system.

**Acceptance Scenarios**:

1. **Given** a signed-in end user, **When** they exercise the customer sample flow, **Then** the
   request is accepted only with a validated identity, the response carries the correlation
   identifier the request was given, and the resulting record is bound to that user's organisation.
2. **Given** a signed-in staff member, **When** they exercise the staff sample flow against a
   customer organisation's record, **Then** the target organisation is derived from durable platform
   state rather than from anything the request asserted.
3. **Given** the workload principal, **When** it exercises the workload sample flow, **Then** it
   authenticates as an application rather than as a person, and carries no customer-organisation
   authority of its own.
4. **Given** one deployable calling another, **When** the call is made, **Then** the caller
   authenticates as itself and the callee rejects an unauthenticated or wrongly-scoped caller.
5. **Given** a sample flow that changes state, **When** the change commits, **Then** the state change
   and its outbox message are durable together or not at all, and a crash between them loses neither
   and duplicates neither.
6. **Given** a durable outbox message, **When** the dispatcher publishes it, **Then** a consumer
   receives it, processes it exactly once in effect, and the same message delivered twice produces
   one outcome.
7. **Given** a completed sample flow, **When** the originating client is connected, **Then** it
   receives a notification carrying no authority — and the flow's outcome is unchanged if the client
   was disconnected throughout.
8. **Given** any of the flows above, **When** its telemetry is inspected, **Then** one correlation
   identifier ties the whole journey together across every tier and every asynchronous hop.
9. **Given** a deployed environment, **When** any component authenticates to a platform resource,
   **Then** it does so as a managed identity, and every secret it needs is resolved by reference at
   the point of use.
10. **Given** a running service, **When** its API contract is requested, **Then** the contract is
    emitted from the running service and matches what the service actually accepts.
11. **Given** RagCore and an inert reference connector reachable only from the Integrations Service,
    **When** RagCore attempts to reach that connector directly, **Then** the attempt fails at the
    network layer — and its attempt to resolve a connector credential fails at the secret store,
    because its identity holds no such role.
12. **Given** RagCore needing the tool catalogue or an inert system-of-record operation, **When** it
    calls the Integrations Service, **Then** the call traverses the API gateway and authenticates as
    an application — and a call arriving by any other route fails, including one carrying a
    well-formed but self-supplied identity contract.
13. **Given** an inert capability to execute, **When** RagCore dispatches it, **Then** the command
    travels over the message transport carrying only an opaque job identifier and correlation
    context, the Integrations Service reads its instruction from the durable job record, and the
    result returns over a separate queue.
14. **Given** the same execution command delivered twice, **When** both are processed, **Then**
    exactly one external effect occurs — and the proof identifies **which** boundary absorbed the
    duplicate, failing if that boundary alone is removed.
15. **Given** a command carrying an organisation field it may not carry, **When** it is received,
    **Then** it is refused and dead-lettered with an alert rather than processed — and separately, a
    valid command whose payload asserts a conflicting organisation still produces an effect bound to
    the organisation on the durable record.
16. **Given** a completed execution, **When** its result returns, **Then** it is matched to the work
    item that originated it, and one correlation identifier is recoverable across the gateway hop,
    both queues and all three deployables.
17. **Given** the Integrations Service under load, **When** its telemetry is inspected, **Then** it
    appears as a distinct source, emits connector-invocation metrics, and its execution records are
    queryable without reference to RagCore.

---

### Edge Cases

- **The requester loses access while work is suspended.** Approved work continues under the platform's
  own execution identity. Revoking a user's access does not by itself cancel authorized work.
- **The requester's organisation is deactivated while work is suspended.** The work does not execute.
- **Two decisions arrive for the same approval.** The first valid decision wins; later ones are
  recorded but do not change the outcome.
- **A session needs a second approval.** One case carries at most one approval, so a second
  consequential operation escalates rather than raising a second approval. *(Inherited open item —
  see Dependencies.)*
- **The notification channel is unavailable.** The platform continues; clients recover state by
  querying rather than by waiting for a push. No state is lost and nothing is authorized differently.
- **A decision is attempted over the notification channel.** It confers no authority and is rejected.
- **The same resume signal is delivered more than once.** The work executes at most once.
- **An operation is cancelled while suspended.** Cancellation is permitted before execution begins;
  once execution has begun, it completes and the outcome is recorded normally.
- **Knowledge is missing but the agent is confident it could act.** Confidence in ability never
  substitutes for evidence; the knowledge gate may withhold but never authorize.
- **An external system reports success but the real state disagrees.** Verification against real state
  governs; a success response is not proof of resolution.
- **A request arrives for a use case placeholder.** UC-01 through UC-12 are undefined, so the request
  falls back to manual resolution.
- **A user attempts to act on another organisation's data.** The request is refused; organisation scope is derived,
  never supplied.
- **A third-party system advertises a capability nobody registered.** It is not callable. Discovery
  does not create entitlement.
- **A third-party system returns content that reads like an instruction.** It is treated as data.
  A successful injection can at most produce a bad proposal, which governance and approval must catch.
- **A third-party system is entitled to one organisation but not another.** The capability resolves
  only where entitled; there is no global toolset.
- **A staff member signs in to a customer surface.** They are an end user there, with end-user
  permissions only. Their staff roles are not consulted and grant nothing on that surface.
- **A staff member has their own IT problem.** They raise it through a customer surface like anyone
  else. The staff portal offers no way to start a session.
- **A technician takes over a session and then needs a consequential action.** They are an additional
  sender in someone else's session, not its requester, so consent for that person's own account or
  device still belongs to the original end user.

## Requirements *(mandatory)*

### Functional Requirements

**Retired identifiers.** These IDs are permanently withdrawn and MUST NOT be reused:

| Retired | Reason | Superseded by |
|---|---|---|
| `FR-EXT-019` | Duplicated the single-boundary and no-leak rule | `FR-EXT-011` |

**Canonical term.** This specification says **organisation** for a customer identity boundary. The
platform specification and the technical artifacts derived from this one — the data model and the API
contracts — use **tenant** and `tenant_id` for the same concept. They are the same thing; the business
term is used here and the technical term there. The phrase *tenant isolation* is retained only where it
names the verification class defined in the constitution.

**Execution treatment.** The four treatments referenced throughout this document are defined in
`Synthia-Platform-Specification.md` §4.3 and are named here so no reader has to assume them:

| Treatment | Meaning |
|---|---|
| `AUTO` | Proceeds without a human decision |
| `END_USER_APPROVAL` | Requires the requester's consent, for an operation on their own account or device |
| `STAFF_APPROVAL` | Requires a staff verdict from a principal holding a role the operation accepts |
| `NOT_ALLOWED` | Refused at the gate; never surfaced to any human as an approvable proposal |

The set is closed, and deterministic governance assigns the treatment from the catalogue
(FR-AGENT-004). Nothing in this document redefines them.

**Verification.** Acceptance of any change against these requirements is demonstrated by the
verification classes defined in the project constitution — unit, integration, contract, architecture,
security, authorization matrix, tenant isolation, adversarial retrieval, checkpoint and resume,
idempotency and concurrency, and frontend and Electron security. They are named there rather than
duplicated here so a single list governs.

**Identifiers are permanent.** Requirements carry a stable ID of the form `FR-<GROUP>-<NNN>` and
success criteria `SC-<GROUP>-<NNN>`, using the same group names. The group names the area; the number
is assigned once and never changes.

| Rule | |
|---|---|
| **Never renumber** | An ID stays with its requirement for the requirement's life. Inserting a new requirement anywhere does not shift any existing ID |
| **Never reuse** | A retired requirement's ID is never reassigned. Gaps in a sequence are expected and correct |
| **Append within a group** | A new requirement takes the next unused number **in its group**, wherever it sits in the document |
| **Groups are stable** | Moving a requirement between groups retires the old ID and issues a new one, with the old recorded as superseded |

Numbers ascend within each group but carry no ordering meaning: `FR-EXT-020` is not "after"
`FR-EXT-001` in any sense that matters. Downstream documents cite these IDs, so a renumber silently
invalidates every citation — which is why renumbering is prohibited rather than discouraged.

The same rules govern `SC-` identifiers, and the shared group names let a criterion be matched to the
requirements it measures: `SC-AUTHZ-001` verifies the `FR-AUTHZ-*` family. Non-binding performance
targets keep the separate `PT-` prefix precisely so they can never be mistaken for acceptance
criteria.

#### Product scope and use cases

- **FR-SCOPE-001**: The platform MUST operate as an autonomous IT service management agent for multiple
  customer organisations from a single deployment.
- **FR-SCOPE-002**: The initial product release MUST contain exactly twelve predefined use cases, identified
  UC-01 through UC-12.
- **FR-SCOPE-003**: The scaffold MUST represent UC-01 through UC-12 as placeholders explicitly marked
  *awaiting product definition*, and MUST NOT contain invented definitions for any of them.
- **FR-SCOPE-004**: The scaffold MUST include a small set of **reference operations** in the governance
  catalogue — one for each execution treatment — so that the catalogue is populated, deterministic
  treatment classification is exercisable, and the sample flows of FR-DEMO-001 onward have something
  inert to act upon before any use case exists.
  *Amended 2026-09-16*: this requirement previously required the consent and approval paths to be
  demonstrable end to end. That demonstration is no longer scaffold scope (FR-DEMO-016). The
  reference operations themselves, one per treatment, are unchanged — the catalogue still carries all
  four treatments, because the treatment a capability is classified under is catalogue data whether
  or not a workflow acts on it.
- **FR-SCOPE-005**: Reference operations MUST be inert. They MUST NOT produce any real effect in any external
  system, and MUST NOT modify any account, device or record.
- **FR-SCOPE-006**: Reference operations MUST be explicitly labelled as scaffold fixtures, MUST NOT be
  presented to any user as product capability, and MUST be excluded from production configuration.
- **FR-SCOPE-007**: Reference operations MUST NOT be counted as, substituted for, or allowed to become any of
  UC-01 through UC-12.
- **FR-SCOPE-008**: A request that matches no defined use case is unsupported, and MUST be handled
  under the manual-fallback rules (FR-FALL-001 onward). This group states *when* a request is
  unsupported; the fallback group states *what happens* to it.
- **FR-SCOPE-009**: The platform MUST decline requests outside IT service management and steer the
  conversation back to its service function.
- **FR-SCOPE-010**: An IT question with no organisational answer MUST be treated as in scope and routed to
  the vendor-documentation fallback, not declined as out of scope.

#### Scaffold demonstration

*Added 2026-09-16 (Clarifications, Session 2026-09-16).* **This group, and only this group, defines
what must be working before the scaffold is complete.** Every other requirement in this document
describes the platform Synthia becomes once it carries product; those requirements are unchanged.

The flows below are the acceptance surface of User Story 6. Each is *representative* — the smallest
flow that genuinely traverses the seam it exists to prove. A flow that does more is not a better
proof; it is a proof with more places to hide.

**Traceability.** This document describes capabilities rather than products, as it does throughout;
[plan.md](./plan.md) names the technology each one resolves to. The mapping is one to one, and is
recorded here so a reviewer can check the scaffold against the component list without inferring it:

| Requirement | Flow | Realised by (plan.md) |
|---|---|---|
| FR-DEMO-001 | Customer API sample flow | Customer audience, behind the edge and the API gateway |
| FR-DEMO-002 | Staff API sample flow | Staff audience |
| FR-DEMO-003 | Workload API sample flow | Workload audience |
| FR-DEMO-004 | Service-to-service, both forms | Async: Service Bus + published views. Sync: workload audience **via APIM** |
| FR-DEMO-004a | No direct service-to-service route | APIM as the sole trust boundary; no pod-to-pod path |
| FR-DEMO-005 | Persistence flow | PostgreSQL — the authoritative durable store |
| FR-DEMO-006 | Transactional outbox flow | PostgreSQL outbox table plus its dispatcher |
| FR-DEMO-007 | Publish and consume flow | Azure Service Bus |
| FR-DEMO-008 | Notification flow | Azure SignalR |
| FR-DEMO-009 | Correlation and trace propagation | W3C Trace Context across all three deployables |
| FR-DEMO-010 | Organisation propagation and isolation | Trusted tenant binding, every tier |
| FR-DEMO-011 | Managed-identity authentication | Entra managed identity to every platform resource |
| FR-DEMO-012 | Secret binding by reference | Azure Key Vault |
| FR-DEMO-013 | Contract emission | OpenAPI, generated from the running services |
| FR-DEMO-020 | Inert reference connector | Reachable only from the Integrations Service |
| FR-DEMO-021 | RagCore cannot reach an external connector | Bypass attempted and observed to fail |
| FR-DEMO-022 | Synchronous Integrations call | Through APIM; catalogue and inert system-of-record operation |
| FR-DEMO-023 | Asynchronous tool execution | Service Bus command and result, separate queues |
| FR-DEMO-024 | Duplicate delivery, one effect | Both idempotency boundaries, proven independently |
| FR-DEMO-025 | Organisation not taken from a payload | Refused **and** bound from durable state |
| FR-DEMO-026 | Connector secrets unreachable by RagCore | Key Vault role held by Integrations alone |
| FR-DEMO-027 | Result correlation to the originating work | One identifier across gateway, both queues, both services |
| FR-DEMO-028 | Integrations independently observable | Distinct source, own metrics, own execution records |

The audiences, the bounded contexts and the deployable boundaries are **unchanged** by this
correction. Nothing above introduces a component, a context or a boundary that
[plan.md](./plan.md) did not already carry.

- **FR-DEMO-001**: The scaffold MUST demonstrate a **customer API sample flow**: a request from an
  authenticated end user, accepted on the customer audience, producing an observable outcome bound to
  that user's own organisation.
- **FR-DEMO-002**: The scaffold MUST demonstrate a **staff API sample flow**: a request from an
  authenticated staff principal, accepted on the staff audience, whose target organisation is derived
  from durable platform state and never from a client-supplied value.
- **FR-DEMO-003**: The scaffold MUST demonstrate a **workload API sample flow**: a request from the
  application principal, accepted on the workload audience, carrying no customer-organisation
  authority of its own.
- **FR-DEMO-004**: The scaffold MUST demonstrate **service-to-service interaction in both of its
  permitted forms**, in each of which the caller authenticates as itself and the callee refuses an
  unauthenticated or wrongly-scoped caller:
  - **Asynchronous** — one service commits a state change, and another observes it through the
    message transport and the published read views. The two sides share no application dependency in
    either direction.
  - **Synchronous** — one service reaches another through the **workload audience**, app-only,
    carrying no customer-organisation authority of its own.
- **FR-DEMO-004a**: **A service MUST NOT reach another service directly.** Every synchronous
  service-to-service call MUST route through the API gateway, which is the platform's trust boundary
  and the single place identity is derived. A direct route between deployables — pod to pod, container
  to container, or by any internal address that bypasses the gateway — MUST NOT exist, and the
  scaffold MUST demonstrate that no such route is reachable.
  *This is the no-direct-service-to-service rule, and it is why FR-DEMO-004 has the shape it does: an
  ordinary HTTP call from one deployable to the other would be the single fastest way to lose the
  boundary that ADR-0001 exists to hold.*
- **FR-DEMO-005**: The scaffold MUST demonstrate a **persistence flow** against the authoritative
  durable store: a write, a read back, and a concurrent write that resolves to exactly one outcome.
- **FR-DEMO-006**: The scaffold MUST demonstrate a **transactional outbox flow** in which a state
  change and the message announcing it become durable in the same transaction, so that a failure
  between them loses neither and duplicates neither.
- **FR-DEMO-007**: The scaffold MUST demonstrate a **publish and consume flow** over the message
  transport, in which a message delivered more than once produces exactly one effect.
- **FR-DEMO-008**: The scaffold MUST demonstrate a **notification flow** to a connected client. The
  notification MUST carry no authority, and the outcome of the originating flow MUST be identical
  when no client is connected at all.
- **FR-DEMO-009**: The scaffold MUST demonstrate **correlation propagation**: one identifier,
  originating at the public edge, appearing on every log record, trace, message and durable record
  belonging to a single journey, across every tier and every asynchronous hop.
- **FR-DEMO-010**: The scaffold MUST demonstrate **organisation propagation and isolation**: the
  organisation binding travelling with the work across every hop, and a request scoped to one
  organisation returning no other organisation's data on any path.
- **FR-DEMO-011**: The scaffold MUST demonstrate **managed-identity authentication** to every platform
  resource it reaches, with no shared key, connection secret or password used to reach any of them.
- **FR-DEMO-012**: The scaffold MUST demonstrate **secret binding by reference**: every credential
  resolved from the secret store at the point of use, with no secret value in source, in tests, or in
  committed configuration.
- **FR-DEMO-013**: The scaffold MUST demonstrate **contract emission**: the API contract for each
  audience generated from the running service, matching what that service actually accepts, rather
  than maintained by hand alongside it.
- **FR-DEMO-014**: Every sample flow MUST act **only on inert reference operations**. No sample flow
  may produce a real effect in any external system, or modify any account, device or record.
- **FR-DEMO-015**: A sample flow MUST NOT implement, stand in for, or be counted as any of UC-01
  through UC-12, and MUST NOT be presented to any user as product capability.
- **FR-DEMO-016**: The scaffold MUST NOT implement `STAFF_APPROVAL` workflow behaviour,
  `END_USER_APPROVAL` workflow behaviour, an approval user interface, a consent user interface, real
  endpoint execution, or desktop script execution. These are platform behaviours, specified elsewhere
  in this document and deferred past the scaffold.
- **FR-DEMO-017**: FR-DEMO-016 defers a **demonstration, not a design**. The four execution
  treatments, the deterministic control gate, durable suspension and resume, and the approval and
  consent authority models remain specified requirements of the platform and MUST NOT be removed,
  weakened or reinterpreted on the strength of that deferral. Any capability reaching the endpoint or
  an external system arrives through them when it arrives.
- **FR-DEMO-018**: The absence of an approval or consent workflow MUST NOT be implemented as a
  permissive default. Where the gate is not yet exercised, an operation requiring a human decision
  MUST be refused or routed to manual fallback — never auto-approved, and never allowed to proceed
  because nothing was there to stop it.
- **FR-DEMO-019**: Every sample flow MUST be exercised **through the real deployed path** — the
  public edge, the web application firewall, the API gateway and the container platform — in a
  deployed environment. A flow driven against a deployable directly, or against a locally hosted
  service, does not satisfy FR-DEMO-001 through FR-DEMO-013.
  - A flow with an asynchronous tail is **entered** through that path; its continuation over the
    message transport is the seam FR-DEMO-004 exists to prove and legitimately leaves it. What MUST
    NOT happen is a flow *entered* by any other route.
  - **Configuration review does not substitute for traversal.** A gateway policy that is correct in
    a template and unreached at runtime protects nothing, and the failure it hides — something
    bypassing the boundary — is invisible to every test that does not actually cross it.

**Proving the Integrations Service boundary.** *(added 2026-09-18)*

These eight demonstrations exist because a boundary that is only described is a boundary that erodes.
Every one is exercised against **inert reference fixtures** and reaches no real external system
(FR-DEMO-014), and every one is driven through the real deployed path (FR-DEMO-019).

- **FR-DEMO-020**: The scaffold MUST provide an **inert reference connector** — a stub external
  endpoint reachable **only** from the Integrations Service. It produces no real effect, is excluded
  from production configuration, and MUST NOT be counted as any of UC-01 through UC-12. It is what
  makes FR-DEMO-021 through FR-DEMO-023 provable without a real external system.
- **FR-DEMO-021**: The scaffold MUST demonstrate that **RagCore cannot reach an external connector**,
  by attempting the bypass and observing it fail — not by asserting an absence. Three proofs, and all
  three are required:
  1. RagCore's attempt to reach the inert reference connector directly fails at the network layer;
  2. RagCore's attempt to resolve a connector credential fails at the secret store, because its
     identity holds no such role;
  3. an architecture check asserts no adapter, connector or external-provider client remains in
     RagCore.

  *An assertion that something is absent passes equally on a system where the path exists and simply
  has no caller yet. Attempting it is what distinguishes the two.*
- **FR-DEMO-022**: The scaffold MUST demonstrate a **synchronous Integrations call through the API
  gateway**: RagCore reads the tool catalogue, and performs an inert case-like system-of-record
  operation, over the gateway-routed path, authenticating as an application. A call that reached the
  Integrations Service by any other route MUST fail — **including one carrying a well-formed but
  self-supplied identity contract**, which is the shape a real bypass takes.
- **FR-DEMO-023**: The scaffold MUST demonstrate **asynchronous tool execution over the message
  transport**: a command from RagCore, an execution against the inert reference connector, and a
  result returned over a separate queue.
- **FR-DEMO-024**: The scaffold MUST demonstrate that **duplicate delivery produces one effect, at
  both boundaries, proven independently**:
  1. a duplicate resume trigger is absorbed by the **atomic claim** in RagCore;
  2. a redelivered execution command is absorbed by the **derived idempotency key** in the
     Integrations Service.

  Each proof MUST fail if its own boundary alone is removed. *A single end-to-end duplicate test
  passes whenever either mechanism holds, and would therefore stay green on the day one of them
  silently stopped working — which is the failure the two-boundary design exists to survive.*
- **FR-DEMO-025**: The scaffold MUST demonstrate that **organisation context is not accepted from a
  command payload**, in two distinct ways:
  1. a command carrying an out-of-contract organisation field is **refused** and dead-lettered with
     an alert, and never processed;
  2. the effect of a valid command is **bound to the organisation on the durable record** even when a
     conflicting one is asserted.

  *The first proves the payload contract is closed; the second proves where the organisation actually
  came from. Neither alone proves both.*
- **FR-DEMO-026**: The scaffold MUST demonstrate that **connector secrets are never available to
  RagCore**: no connector credential is resolvable by RagCore's identity, none appears in its
  configuration, environment or image, and the Integrations Service is the sole holder of that role.
- **FR-DEMO-027**: The scaffold MUST demonstrate **result correlation back to the originating work**:
  an execution result returned over the message transport is matched to the work item that originated
  it, and one correlation identifier is recoverable across the gateway hop, both queues and both
  services.
- **FR-DEMO-028**: The scaffold MUST demonstrate that the **Integrations Service is independently
  observable**: it appears as a distinct source in traces and logs; it emits connector-invocation
  metrics covering attempts, outcomes and duration; and its execution records are queryable without
  reference to RagCore — while the platform's single correlation identifier still spans the whole
  journey.

#### Personas and authorization

- **FR-AUTHZ-001**: The platform MUST distinguish two persona classes: `end_user` — any person acting on a
  customer surface, **including a Synoptek staff member doing so** — and `staff`, a Synoptek person
  acting on the staff surface. The same person is one or the other depending only on the surface they
  entered through.
- **FR-AUTHZ-002**: The platform MUST support three staff roles: `technician`, `senior_technician` and
  `administrator`.
- **FR-AUTHZ-003**: Staff roles MUST be independent capabilities with no hierarchy, ranking or precedence.
  Holding `administrator` MUST NOT imply `technician`.
- **FR-AUTHZ-004**: Staff authorization MUST be decided by set intersection between the roles a person holds
  and the roles an operation accepts. An empty intersection MUST deny.
- **FR-AUTHZ-005**: Every operation MUST explicitly declare the set of roles it accepts.
- **FR-AUTHZ-006**: A person holding multiple roles MUST receive the union of those capabilities and nothing
  further.
- **FR-AUTHZ-007**: In the initial release, `technician` MUST be the role that may approve, and
  `administrator` MUST NOT be able to approve.
- **FR-AUTHZ-008**: `senior_technician` MUST exist as a defined role that no operation in the initial release
  accepts.
- **FR-AUTHZ-009**: Customer authorization and staff authorization MUST be separate models; a rule written
  for one MUST NOT decide the other.
- **FR-AUTHZ-010**: An operation that accepts no roles MUST deny every caller. An empty accepted-role
  set is a total denial, never an implicit allow.
- **FR-AUTHZ-011**: Authorization MUST be evaluated against the roles held at the moment of decision,
  and that role set MUST be recorded with the decision. A later change to a person's roles MUST NOT
  retroactively alter a recorded decision, and MUST NOT by itself cancel work already authorized.

#### Identity and security behaviour

- **FR-IDENT-001**: Human identity MUST be established solely from the organisation's enterprise identity
  provider. The platform MUST NOT issue, store or broker user credentials.
- **FR-IDENT-002**: A user MUST NOT be able to choose, supply or influence their own organisation, roles,
  privileges or audience. All are derived from validated identity.
- **FR-IDENT-003**: Model output MUST NOT confer authority of any kind.
- **FR-IDENT-004**: Retrieved content, external tool output and chat text MUST NOT confer authority.
- **FR-IDENT-005**: The realtime notification channel MUST NOT authorize any consequential action. It may
  announce that something exists or has changed; a decision MUST arrive through an authenticated
  request that identifies the decider.
- **FR-IDENT-006**: An end user MUST be confined to their own organisation and their own records.
- **FR-IDENT-007**: Staff MUST operate across customer organisations using trusted platform context; the
  target organisation MUST be derived from the work, never supplied by the staff member.
- **FR-IDENT-008**: Organisation scope MUST be enforced at every layer, including knowledge retrieval, where
  filtering MUST be mandatory and non-bypassable.
- **FR-IDENT-009**: Knowledge retrieval MUST NOT return content belonging to another organisation under any
  circumstances, including deliberately crafted input.
- **FR-IDENT-010**: Aggregated and derived figures MUST NOT reveal another organisation's data through
  counts, rankings, distributions or any other indirect route. A figure spanning organisations MUST be
  exposed only where no single organisation's contribution is identifiable.
- **FR-IDENT-011**: Identity MUST be derived exactly once, at the gateway, and stated to services in a
  **closed header contract of exactly five values**: the identity-provider tenant, the principal object
  identifier, the complete role set in canonical order, the credential class (`delegated` or `app`), and
  the client application identifier. A service MUST NOT parse an access token, MUST NOT accept an
  identity header outside this set, and MUST refuse a contract whose role value is absent, empty,
  unordered, duplicated, whitespace-padded or outside the canonical set. The gateway MUST delete every
  inbound copy of these headers before validation and set them on the outbound request.
  **The audience is NOT among them.** It is fixed by the route the gateway matched, because the surface
  decides which authorization model applies (FR-SURF-005). An audience carried as a header would be an
  authority field a client could write — the self-promotion FR-IDENT-002 exists to prevent.
- **FR-IDENT-012**: A service MUST be able to distinguish a header contract set by the gateway from one
  supplied by a caller, and MUST refuse any request on an audience path that cannot prove gateway
  provenance. **Network placement alone MUST NOT be treated as that proof**: an internal-only service is
  reachable by everything already inside its network boundary, and for a service that consumes the
  contract as authoritative, reachability *is* the ability to assert any organisation and any role. The
  request MUST be refused rather than sanitised — stripping the headers and continuing returns success
  to an attacker and leaves the attempt indistinguishable from an ordinary unauthenticated call.

#### Client surfaces

- **FR-SURF-001**: The platform MUST provide three client surfaces: a customer portal, a customer desktop
  application, and a staff portal.
- **FR-SURF-002**: A user MUST sign in before any surface presents platform content.
- **FR-SURF-003**: The staff portal MUST present only the modules the signed-in person's roles grant.
- **FR-SURF-004**: No client surface MUST make an authorization, tenancy or policy decision. Client-side
  role checks are presentation only and MUST be re-decided server-side.
- **FR-SURF-005**: The surface a person enters through MUST determine which persona and authorization model
  applies to them. A person MUST NOT be able to promote themselves to staff by anything they supply in
  a request.
- **FR-SURF-006**: The staff portal MUST NOT provide any facility to start a chat session or raise a support
  request. It exists for staff to work on other people's sessions, not to originate their own.
- **FR-SURF-007**: A Synoptek staff member who needs to raise their own request MUST do so through a
  customer surface.
- **FR-SURF-008**: Every person acting on a customer surface MUST be treated as an end user, regardless of
  any staff roles they hold. No staff role check MUST be applied on a customer surface, and holding a
  staff role MUST confer no additional capability there.
- **FR-SURF-009**: Take-over MUST be participation in an existing end-user session as an additional sender.
  It MUST NOT constitute origination of a staff-owned session, and it MUST NOT grant the staff member
  the requester's authority over the work.
- **FR-SURF-010**: All three client surfaces MUST conform to WCAG 2.2 Level AA. The staff portal is held to
  the same level as the customer surfaces; there is no best-effort surface.
- **FR-SURF-011**: Progressively delivered response content MUST be conveyed to assistive technology as it
  arrives, **announcing only the text not already announced**. Re-announcing content the user has
  already heard MUST NOT occur, so a growing response is never read back from the beginning as each
  fragment arrives.
- **FR-SURF-012**: Consent prompts, approval decisions and the approval queue MUST be fully operable by
  keyboard alone and MUST be conveyed to assistive technology, because they carry consequential
  decisions and MUST NOT depend on pointer interaction or visual-only cues.
- **FR-SURF-013**: A suspended, pending or expired state MUST be conveyed by more than colour alone.
- **FR-SURF-014**: The scaffold MUST support English only, for both interface text and agent responses.
  Localization infrastructure — externalized strings, locale negotiation, translated content — is
  explicitly NOT required.
- **FR-SURF-015**: The scaffold MUST operate from a single region serving all organisations. Per-organisation
  data residency is explicitly NOT required, and no region attribute is carried on the organisation
  record.
- **FR-SURF-016**: Every surface MUST define and present loading, empty and partial-failure states for
  each primary journey. A failure MUST NOT be presented as an empty result.
- **FR-SURF-017**: A client MUST address the platform through a single gateway. Which backend serves a
  given operation MUST NOT be a client concern, and no client MUST be configured with more than one
  platform origin.
- **FR-SURF-018**: A client MUST NOT treat a notification as authority. Any consequential action
  prompted by a notification MUST be performed through an authenticated request that is authorized
  independently of that notification.

#### Conversation and session behaviour

- **FR-SESS-001**: A user MUST be able to start a chat session and send messages in natural language.
- **FR-SESS-002**: A response MUST be able to stream progressively rather than appearing only when complete.
- **FR-SESS-003**: A work record MUST be committed only when the user has articulated a genuine
  problem — a turn that states a problem or requests an action. Greetings, small talk and
  meta-conversation about the assistant itself MUST create nothing.
- **FR-SESS-004**: One chat session MUST correspond to exactly one work record.
- **FR-SESS-005**: A session MUST survive client disconnection. Closing a client ends presence, not work.
- **FR-SESS-006**: A user MUST be able to return to a session and find its prior context intact.
- **FR-SESS-007**: Chat content MUST be retained for 90 days by default, after which it is removed from the
  platform. The durable record of the case lives in the system of record, so the platform's own copy is
  deliberately short-lived to limit how long personal data is held.
- **FR-SESS-008**: The retention window for each data class MUST be overridable per organisation, and the
  platform default MUST apply wherever no override is configured. A missing configuration MUST NOT
  result in unbounded retention.
- **FR-SESS-009**: An end user MUST be able to record feedback against an individual agent-authored message
  in their own session, as a binary positive or negative signal.
- **FR-SESS-010**: Feedback MUST be revisable. A user MUST be able to change or withdraw a signal they
  previously recorded, and only the current signal counts.
- **FR-SESS-011**: Feedback MUST be scoped to the owning organisation and the owning user. A user MUST NOT
  be able to record feedback on another user's session or message.
- **FR-SESS-012**: Feedback MUST be available to reporting in aggregate.
- **FR-SESS-013**: Feedback MUST NOT influence authorization, governance treatment, retrieval scope or
  execution in any way. It is a quality signal and MUST NEVER become an input to a decision.
- **FR-SESS-014**: Feedback MUST follow chat-content retention. Aggregate reporting figures derived from it
  MUST be retained independently, so expiring the underlying signals does not erase reporting history.
- **FR-SESS-015**: A chat session MUST progress through a defined set of states: `conversational`,
  `resolving`, `awaiting_user`, `awaiting_consent`, `awaiting_approval`, `staff_controlled`, and the
  terminal states `resolved`, `escalated` and `closed_declined`.
- **FR-SESS-016**: The three awaiting states MUST persist indefinitely. Losing the realtime connection
  MUST NOT change session state.
- **FR-SESS-017**: An idle connection MAY be closed to control load. A suspended session MUST survive
  that close. Disconnection MUST NOT cancel work, withdraw an approval request, or change any state.
- **FR-SESS-018**: A suspended session MUST be visible to its user as awaiting them, identifying which
  interruption is pending, both within the session and in their session listing.
- **FR-SESS-019**: On reconnect a client MUST rebuild its view from the platform rather than from
  notifications it may have missed.
- **FR-SESS-020**: Content retention MUST be measured from the moment a session reaches a terminal
  state. The content of a session that has not reached one MUST NOT expire, so an indefinitely
  suspended session cannot lose the context it is suspended on.

#### Agent behaviour

- **FR-AGENT-001**: The agent MUST follow a repeating resolution cycle of understanding the request,
  retrieving knowledge, proposing an operation, evaluating it through deterministic governance,
  executing only what is authorized, and verifying the outcome.
- **FR-AGENT-002**: Classification of a request MUST NOT authorize any action.
- **FR-AGENT-003**: Retrieved evidence MUST inform proposals only.
- **FR-AGENT-004**: Deterministic governance MUST be the only point at which an operation is authorized, and
  MUST assign that decision from a defined catalogue rather than from model output.
- **FR-AGENT-005**: Knowledge, ability and security MUST be evaluated as independent conditions; none may
  average away another, and the knowledge condition may withhold but MUST NEVER authorize.
- **FR-AGENT-006**: A raw similarity score MUST NOT be treated as a probability. The knowledge
  condition MUST use absolute score **together with margin** — the gap between the best and
  second-best candidate — so that a near-tie routes differently from a confident single match at the
  same top score.
- **FR-AGENT-007**: Gate thresholds MUST be global constants for the platform, not per-organisation
  configuration, so the resolution loop behaves identically for every organisation.
- **FR-AGENT-008**: Side-effecting operations MUST NOT be directly reachable from an unconstrained agent
  loop.
- **FR-AGENT-009**: The agent MUST verify an outcome against real state. A successful response from an
  external system MUST NOT be treated as proof of resolution.
- **FR-AGENT-010**: The platform MUST record whether an outcome was independently confirmed or only reported,
  and MUST NOT present a merely-reported outcome as confirmed resolution.
- **FR-AGENT-011**: When the agent cannot proceed safely, it MUST escalate for human resolution rather than
  guessing, stubbing a result, or reporting success it cannot support.
- **FR-AGENT-012**: Content MUST be checked for safety before it reaches the model, and again before a
  response returns to a user.
- **FR-AGENT-013**: Retrieved content, third-party output and fetched vendor documentation are data and MUST
  NOT be interpreted as instructions to the agent.
- **FR-AGENT-014**: A successful injection MUST at most produce a bad proposal. It MUST NOT be able to reach
  execution, because the control gate and, where required, human approval stand between a proposal and
  any action.
- **FR-AGENT-015**: Every safety decision MUST be recorded with its correlation identifier.

#### Interruption, suspension and resume

- **FR-INTR-001**: The agent MUST support three interruption types: clarification, end-user consent, and
  staff approval.
- **FR-INTR-002**: An interruption MUST suspend work durably and for an unbounded period.
- **FR-INTR-003**: The prompt for an interruption MAY be delivered over the notification channel; the answer
  MUST arrive through an authenticated request.
- **FR-INTR-004**: A clarification MUST be answerable only by the end user of the session.
- **FR-INTR-005**: Consent MUST be given only by the person who requested the work, and only for an
  operation affecting their own account or device.
- **FR-INTR-006**: Consent MUST be captured as an explicit authenticated action bound to the work. An
  affirmative message in the conversation MUST NOT be treated as consent.
- **FR-INTR-007**: Consent MUST NOT satisfy a requirement for staff approval.
- **FR-INTR-008**: Approval MUST be a human decision. There MUST be no system-generated verdict and no
  approval by timeout.
- **FR-INTR-009**: An approval request MUST disclose every command the operation would perform.
- **FR-INTR-010**: The first valid decision on an approval MUST win; later decisions MUST be recorded but
  MUST NOT change the outcome.
- **FR-INTR-011**: After a decision, work MUST resume automatically from its suspended state without
  requiring any client to be present or to initiate the resume.
- **FR-INTR-012**: Resume MUST continue the response stream rather than restarting the interaction.
- **FR-INTR-013**: A take-over MUST resolve as a single transition. Where two staff attempt it
  concurrently, the first valid transition MUST win and the later MUST be recorded without changing
  ownership.
- **FR-INTR-014**: Cancellation MUST be available at every suspension point — clarification, consent
  and approval — not only while awaiting approval.

#### Execution and governance

- **FR-EXEC-001**: Authorized execution MUST be valid only within a bounded window; after it elapses the work
  becomes non-executable and requires fresh authorization. Expiry MUST NOT be reported as an error.
- **FR-EXEC-002**: Approved work MUST execute even if the requesting user is absent, disconnected, or has
  since lost access.
- **FR-EXEC-003**: Approved work MUST NOT execute if the target organisation is no longer active.
- **FR-EXEC-004**: Execution MUST occur at most once per authorization, even if the resume signal is
  delivered more than once.
- **FR-EXEC-005**: A repeated operation MUST NOT cause a repeated effect in an external system.
- **FR-EXEC-006**: A failed authorized action MUST NOT retry automatically; it MUST require fresh human
  authorization.
- **FR-EXEC-007**: Work that was approved but never executed MUST surface to humans rather than expiring
  silently.
- **FR-EXEC-008**: The authority attributes of a work record MUST be immutable once set.
- **FR-EXEC-009**: Cancellation MUST be permitted before execution begins; once begun, execution completes
  and its outcome is recorded.
- **FR-EXEC-010**: A work record MUST progress through a defined set of states: `open`,
  `awaiting_decision`, `authorized`, `claimed`, `executed`, `failed`, `expired`, `cancelled` and
  `escalated`. Its approval state MUST be one of `none`, `pending`, `approved`, `rejected` or
  `expired`. The two are independent: approval state records what a human decided, work state records
  what happened to the work, and an `approved` work item that never executed MUST be distinguishable
  from one that did.

#### External systems

- **FR-EXT-001**: The platform MUST use ServiceNow as the system of record for cases. It complements the
  existing ITSM queue rather than replacing it.
- **FR-EXT-002**: A case MUST be created when the triage gate fires, carrying at least a short description,
  category, owning organisation and end user. Each chat session MUST be anchored to exactly one case.
- **FR-EXT-003**: The platform MUST write the session's progress to its case: conversation turns and agent
  steps, each policy decision and assigned treatment, a mirror of any approval request and its verdict,
  execution outcomes, and the terminal state.
- **FR-EXT-004**: Writes to the case MUST be idempotent. A retried write MUST NOT double-post.
- **FR-EXT-005**: An inbound state change from the system of record MUST be treated as an untrusted signal.
  It MUST NOT set platform state and MUST NOT authorize execution.
- **FR-EXT-006**: The system of record MUST NOT be an authority for platform approvals.
- **FR-EXT-007**: If the system of record is unavailable, writes MUST queue and replay rather than being
  lost. An outage MUST NOT block the agent loop, but a session that cannot commit a case MUST NOT
  proceed to resolution and the user MUST be told.
- **FR-EXT-008**: The platform MUST integrate with Microsoft Graph for directory and productivity
  operations.
- **FR-EXT-009**: The platform MUST support an **extensible set of third-party target systems** that an
  incident may require reading details from or performing an operation against. OneLogin and Duo are
  the first such systems and are examples, not a closed list.
- **FR-EXT-010**: Adding a further third-party target system MUST require only registering its capabilities
  and their governance treatment. It MUST NOT require a new authorization mechanism, a new approval
  path, or an exception to any existing rule.
- **FR-EXT-011**: All traffic to a given external system MUST pass through a single owning integration
  boundary, and that system's own concepts MUST NOT leak into the platform's model.
- **FR-EXT-012**: Every third-party capability MUST be tagged as either *read* — retrieves state, no side
  effect — or *action* — has a side effect.
- **FR-EXT-013**: An *action* capability MUST NOT be callable directly from the agent loop and MUST pass
  through deterministic governance and, where required, human approval.
- **FR-EXT-014**: Discovery MUST NOT confer entitlement. A capability advertised by a third-party system
  MUST NOT become callable until it is registered in the governance catalogue and entitled to the
  organisation in question.
- **FR-EXT-015**: There MUST be no global capability set. Capabilities MUST resolve per organisation on a
  least-privilege basis.
- **FR-EXT-016**: Credentials for a third-party system MUST be held per organisation and per system,
  resolved from the single secret source, and MUST NEVER appear in conversation, the step trail,
  telemetry or audit records.
- **FR-EXT-017**: Output returned by a third-party system MUST be treated as data. It MUST NOT be treated
  as instruction, and it MUST NOT confer authority.
- **FR-EXT-018**: The destination of an outbound call MUST NEVER be derived from retrieved content, model
  output or chat text.
- **FR-EXT-020**: The platform MUST continue to function in a reduced mode when an external system is
  unavailable, and MUST NOT take an ungrounded action in its absence.
- **FR-EXT-021**: Output from a third-party system that is malformed, oversized, or does not match its
  declared contract MUST be rejected at the integration boundary and MUST NOT reach the agent loop or
  the domain.
- **FR-EXT-022**: A capability that is entitled but whose system is unreachable MUST be reported as
  temporarily unavailable, distinctly from one that is not entitled. Neither MUST be presented to the
  user as a failure of their request.

#### The Integrations Service

Derived from `Synthia-Platform-Specification.md` §21.6 and ADR-0007, which are authoritative. These
requirements state what the scaffold must build; they do **not** decide architecture, and any
divergence between them and the platform specification is resolved in the specification's favour.

**Responsibilities.**

- **FR-INTEG-001**: The platform MUST deploy **Integrations as a service separate from RagCore**, with
  its own runtime, its own workload identity and its own lifecycle.
- **FR-INTEG-002**: The Integrations Service MUST own the **tool catalogue** — the capability set
  resolved for one organisation — and expose it for synchronous read.
- **FR-INTEG-003**: It MUST own the **connector registry**: how a capability executes — connector,
  endpoint, signing profile and idempotency policy.
- **FR-INTEG-004**: It MUST own **tenant tool configuration**: which capabilities an organisation may
  use. There MUST be no global capability set.
- **FR-INTEG-005**: It MUST own **operation execution**, the **MCP client**, **MCP connector and server
  integration**, and **all external API calls** — ServiceNow, Microsoft Graph, OneLogin, Duo and every
  further system.
- **FR-INTEG-006**: It MUST own **credential lookup**, **result normalization**, **external
  idempotency**, **execution records**, and its own **telemetry, audit and trace** emission.

**Non-responsibilities.**

- **FR-INTEG-007**: The Integrations Service MUST NOT implement user conversation, reasoning, graph
  orchestration, **tool-selection reasoning**, approval waiting or its user interface, or graph
  interrupt and resume.
- **FR-INTEG-008**: It MUST NOT assign **execution treatment** and MUST NOT perform **role-set
  intersection**. Those are deterministic governance's decisions, and a second authority for either
  could disagree with the first.
- **FR-INTEG-009**: It MUST NOT perform final issue verification's **conclusion**, nor decide to close
  a case. It reports what it observed; RagCore decides what that means.
- **FR-INTEG-010**: It MUST NOT perform the **atomic claim**. Idempotency boundary 1 belongs with the
  authority record in RagCore.

**Communication paths.** Exactly three, and no other path exists.

- **FR-INTEG-011**: **Synchronous catalogue access.** RagCore MUST read the tool catalogue over
  synchronous HTTPS, routed through the public edge and the **API gateway**, authenticating as an
  application with its own distinct application role. The request MUST carry an opaque identifier and
  MUST NOT carry an organisation.
- **FR-INTEG-012**: **Synchronous system-of-record operations.** Where the platform must know the
  outcome before proceeding, RagCore MUST reach ServiceNow **through the Integrations Service**, over
  the same gateway-routed path.
- **FR-INTEG-013**: **Asynchronous tool execution.** Normal tool execution MUST travel RagCore →
  message transport → Integrations Service, and its result MUST return Integrations Service → message
  transport → RagCore, over queues of their own, separate from the resume trigger.
- **FR-INTEG-014**: **The command MUST carry only an opaque job identifier, correlation identifiers
  and a routing kind.** RagCore MUST write the capability, its version and its parameters to a durable
  job record before the message exists, and the Integrations Service MUST read its instruction from
  that record and **never from the message**.
- **FR-INTEG-015**: **A direct route between deployables MUST NOT exist.** RagCore MUST NOT reach the
  Integrations Service other than through the gateway, and the Integrations Service MUST NOT trust an
  identity header a caller supplied.

**Security and isolation.**

- **FR-INTEG-016**: **RagCore MUST NOT hold, resolve or be able to resolve any connector credential**,
  and MUST NOT have a network path to any external system. The Integrations Service MUST be the sole
  holder of the secret-store role for connector credentials.
- **FR-INTEG-017**: Every component MUST authenticate as a **managed identity** to every platform
  resource that supports it, and connector credentials MUST resolve from the **secret store** by
  reference at the point of use, per organisation and per system.
- **FR-INTEG-018**: The Integrations Service MUST resolve the organisation **only from durable
  state** — the job record on the asynchronous path, the durable object an opaque identifier names on
  the synchronous path. It MUST NOT accept an organisation from a request field, a message payload, a
  token, model output or tool output.
- **FR-INTEG-019**: **At execution time, and against durable state**, the Integrations Service MUST
  re-verify: the organisation is active; the work is authorized, uncancelled and within its execution
  window; the organisation is entitled to the capability; the capability is registered; its version
  matches what was authorized; and the capability was reached past the control gate. Prior catalogue
  retrieval MUST NOT be treated as standing permission.
- **FR-INTEG-020**: The Integrations Service MUST NOT be able to modify the instruction it was given.
  It MAY write the result of a job record and MUST NOT be able to alter the capability, its version,
  its parameters or its organisation.

**Execution integrity and operation.**

- **FR-INTEG-021**: **Connector idempotency.** Every outbound call MUST carry a **derived**, never
  random, idempotency key, so a redelivered command produces the same key and therefore at most one
  external effect. This boundary MUST NOT substitute for the atomic claim, nor the claim for it.
- **FR-INTEG-022**: **Execution records.** The Integrations Service MUST durably record what was
  attempted externally — connector, endpoint, derived key, external reference and normalized outcome
  — distinctly from the platform's own conclusion about the operation.
- **FR-INTEG-023**: **Result normalization.** Provider output MUST be parsed and contract-checked at
  the boundary and treated as data. It MUST NOT become an instruction, a destination, an identity, an
  organisation or a source of authority.
- **FR-INTEG-024**: **Telemetry, audit and traceability.** The service MUST appear as a distinct
  source in traces and logs; MUST emit connector-invocation metrics; MUST make its execution records
  queryable without reference to RagCore; and MUST carry the platform's **single correlation
  identifier** across the gateway hop and the message transport. Audit MUST remain one store, with
  the actor chain recording the Integrations principal as the executing principal. Telemetry MUST NOT
  carry credentials, tokens or cross-organisation information.
- **FR-INTEG-025**: **Contract emission.** The Integrations Service MUST emit its API contract from
  the running service, per audience, never merged with another deployable's, under the same
  publication gates as the existing contracts.
- **FR-INTEG-026**: **Health and readiness.** It MUST expose a process-only liveness signal and a
  readiness signal covering its durable store, its message transport and its secret store. Readiness
  MUST NOT depend on any external customer system, whose unavailability is an operational condition
  rather than an unready service.
- **FR-INTEG-027**: **Resilience, retry and dead-lettering.** Reads MAY retry with backoff inside the
  adapter. A **side-effecting operation MUST NOT be retried automatically**; it requires fresh human
  authorization. Every outbound call MUST carry an explicit timeout. A command that cannot be
  processed within its validity window MUST dead-letter rather than execute, MUST NOT be replayed
  automatically, and where it carried authorized work MUST surface as a governance failure rather
  than an operational one.
- **FR-INTEG-028**: When the Integrations Service is unavailable, conversation, retrieval and guidance
  MUST continue. A capability requiring an external effect MUST fall back to manual resolution or
  escalation, explicitly and visibly.

#### Manual fallback

- **FR-FALL-001**: An unsupported or unresolved request MUST be transferred for human resolution.
- **FR-FALL-002**: An escalated request MUST be placed on the ServiceNow queue, routed according to the
  owning organisation's configured queue mapping.
- **FR-FALL-003**: The escalation MUST carry full context to the queue: the conversation transcript, the
  candidate resolutions the agent considered, and the reason it could not proceed.
- **FR-FALL-004**: Escalation MUST NOT require approval. It is the platform's safety valve and MUST always
  be available.
- **FR-FALL-005**: If the system of record is unavailable at the moment of escalation, the escalation MUST
  queue and replay. It MUST NOT be silently dropped, and the user MUST still be told a human will take
  the request.
- **FR-FALL-006**: Escalation MUST be recorded as an audit event.
- **FR-FALL-007**: A fallback MUST be explicit and visible: stated to the user in the conversation and
  recorded on the case. A log entry alone MUST NOT satisfy this. The platform MUST NOT silently
  degrade, fabricate a result, or present a plausible-looking answer it cannot support.
- **FR-FALL-008**: A transferred request MUST carry its context so a human can continue without the user
  repeating themselves.
- **FR-FALL-009**: Because UC-01 through UC-12 are undefined, the scaffold MUST route every request
  requiring an action to manual resolution.
- **FR-FALL-010**: A fallback MUST tell the user, in plain language, **why** the platform could not
  proceed — not only that it could not.

#### Audit

- **FR-AUDIT-001**: Every consequential action MUST produce a durable record identifying who requested it,
  who approved or consented to it, which principal executed it, by what means, against which
  organisation, and with what result.
- **FR-AUDIT-002**: Audit records MUST be distinguishable from operational telemetry, and telemetry MUST NOT
  substitute for them.
- **FR-AUDIT-003**: Decisions that deny, expire or escalate MUST be recorded as durably as decisions that
  permit.
- **FR-AUDIT-004**: Audit records MUST be retained for 7 years by default. Audit retention MUST be
  independent of chat-content retention; expiring chat content MUST NOT remove the audit record of
  what was done.
- **FR-AUDIT-005**: The agent's working state MUST be retained for 30 days after the work it belongs to
  completes, then removed. It is working state rather than a record, so its removal MUST NOT affect
  the work record or the audit trail.
- **FR-AUDIT-006**: Erasure for an organisation MUST remove that organisation's records, their derived
  representations and any cached copies.

#### Platform operation

- **FR-OPS-001**: A correlation identifier MUST originate at the public edge and be propagated through
  every tier of request handling. It MUST appear on every log record, trace, notification, trigger and
  audit record, so one user request can be followed across an asynchronous, suspendable flow.
- **FR-OPS-002**: The platform MUST emit distributed traces, metrics and structured logs, each tagged
  with the owning organisation from trusted context — never from a supplied header or from message
  content.
- **FR-OPS-003**: Agent-specific signals MUST be observable: model token usage per organisation,
  cache-hit ratio, guardrail actions, control-gate outcome distribution, and retrieval confidence
  distribution.
- **FR-OPS-004**: Telemetry MUST NOT be used to answer a question that audit is responsible for. They
  are separate stores with separate retention.
- **FR-OPS-005**: Per-organisation token, compute and request budgets MUST be enforced, so no single
  organisation's load can degrade another's service.
- **FR-OPS-006**: Where a request is throttled by a budget or rate limit, the user MUST be told the
  request was limited. It MUST NOT be presented as a failure of the request itself.
- **FR-OPS-007**: Every model call MUST pass through a single brokering point. No component MUST be able
  to reach a model provider directly.
- **FR-OPS-008**: The brokering point MUST meter model usage per organisation in provider-neutral units, so
  usage remains comparable when a provider changes.
- **FR-OPS-009**: Model usage MUST NOT be coupled to one provider. Changing or adding a provider MUST NOT
  require a change to the agent, governance, retrieval or execution logic.
- **FR-OPS-010**: Repeated equivalent model requests MAY be served from cache. A cached response MUST be
  attributable and MUST NOT bypass the checks that a fresh response passes.
- **FR-OPS-011**: Telemetry MUST be retained for 30 days by default, overridable per the same
  class-based mechanism as every other data class. Telemetry retention is deliberately far shorter
  than audit retention (FR-AUDIT-004), which is what makes FR-OPS-004 enforceable in practice: a
  question that only audit can answer MUST NOT be answerable from telemetry, and after 30 days it
  demonstrably is not.
- **FR-OPS-012**: Where traces are sampled, sampling MUST be decided per correlated journey rather
  than per request, so that a suspended-and-resumed journey is either wholly sampled or wholly not.
  A sampling strategy that can retain the request half of a journey and discard the resume half MUST
  NOT be used, because it would defeat SC-OPS-001.

### Key Entities

- **Chat session**: One conversation between an end user and the platform. Carries the durable
  authority context for its work. Corresponds one-to-one with a work item.
- **Message**: A single turn in a conversation, from the user, the agent, or a staff member who has
  taken over.
- **Work item**: The durable authority record for a session — organisation, requester, governed action,
  target, approval state, execution validity and outcome. Its authority attributes are immutable.
- **Operation**: A single proposed or executed action within a session, carrying the governance
  decision that determines how it may proceed.
- **Approval**: A staff member's recorded decision authorising a consequential operation. At most one
  per case.
- **Consent**: An end user's recorded agreement to an operation affecting their own account or device.
- **Audit event**: A durable business or security record of a consequential action, distinct from
  telemetry.
- **Governance record**: The catalogue of known operations and the rules that determine how each may
  proceed and which roles may authorize it.
- **Integration job**: The durable instruction handed to the Integrations Service — organisation,
  capability, version and parameters — written before the command that announces it exists, and
  carrying the result written back against it. The Integrations Service reads the instruction and may
  write only the result.
- **Connector binding**: How a capability actually executes — connector, endpoint, signing profile and
  idempotency policy. Owned by the Integrations Service, and distinct from the governance record,
  which says whether and by whom a capability may be used.
- **Execution record**: What was attempted against an external system — connector, endpoint, derived
  idempotency key, external reference and normalized outcome. Distinct from the platform's own
  conclusion about the operation: *what was attempted* and *what the platform concluded* are
  different facts.
- **Inert reference connector**: A stub external endpoint reachable only from the Integrations
  Service, producing no real effect. A scaffold fixture, excluded from production configuration, and
  never one of UC-01 through UC-12.
- **Graph checkpoint**: The agent's working state, allowing durable suspension and resume. Working
  state only — never a source of authority.
- **Organisation mapping**: The record binding a validated organisation identifier to its platform
  representation, status and entitlements.
- **Case**: The record in the system of record that anchors a chat session and carries it into the
  human queue. Owned externally; the platform holds only a reference to it.
- **Feedback**: A per-message thumbs signal recorded by the end user who owns the session. Binary,
  revisable, and never an input to any decision.
- **Use case placeholder**: One of UC-01 through UC-12, marked awaiting product definition, with no
  behaviour of its own.

## Success Criteria *(mandatory)*

These identifiers follow the same permanence rules as requirements — never renumbered, never reused,
appended within their group.

### Measurable Outcomes

#### Scaffold honesty

- **SC-SCOPE-001**: Because no use case is yet defined, 100% of action-requiring requests route to manual
  resolution — and this is reported honestly rather than presented as a failure.
- **SC-SCOPE-002**: Each of the four execution treatments is registered in the catalogue against a
  reference operation, and deterministic classification assigns the treatment the catalogue records
  in 100% of trials, with no real effect occurring in any external system.
  *Amended 2026-09-16*: this criterion previously required each treatment to be demonstrated end to
  end through its workflow. The workflow demonstration is no longer scaffold scope (FR-DEMO-016);
  what remains measurable now is that the catalogue carries all four and that classification is
  deterministic.
- **SC-SCOPE-003**: No reference operation is present in a production configuration, and none is ever
  presented to a user as a product capability.

#### Platform demonstration

*Added 2026-09-16.* **The scaffold is complete when every criterion in this group is met.** Each is
verified against a deployed environment, not a unit test, because the seams these exist to prove are
precisely the ones that do not exist in a single process.

- **SC-DEMO-001**: All thirteen sample flows (FR-DEMO-001 through FR-DEMO-013) **and the nine
  Integrations-boundary demonstrations (FR-DEMO-020 through FR-DEMO-028)** complete successfully when
  driven through the deployed public edge, web application firewall, API gateway and container
  platform, and each is repeatable by an engineer following written steps without recourse to the
  authors. 0 flows are accepted on the strength of a direct-to-deployable or locally hosted run.
- **SC-DEMO-002**: 100% of sample-flow requests are rejected when presented without a valid identity,
  and no flow has an unauthenticated path that succeeds.
- **SC-DEMO-003**: Every hop in every sample flow — client to service, service to service, service to
  platform resource — authenticates, and 0 of them rely on a shared key, connection secret or
  password.
- **SC-DEMO-003a**: 100% of synchronous service-to-service calls route through the API gateway, and
  0 direct routes between deployables are reachable — verified by attempting one and observing it
  fail, not by observing that none is currently used.
- **SC-DEMO-003b**: A request presented directly to a deployable, bypassing the edge and the gateway,
  fails in 100% of attempts across every audience — including a request carrying a well-formed but
  self-supplied gateway header contract, which is the shape a bypass actually takes.
- **SC-DEMO-004**: A repository scan finds 0 secret values in source, in tests and in committed
  configuration; every credential is present only as a reference resolved at the point of use.
- **SC-DEMO-005**: One correlation identifier is recoverable end to end for 100% of sample-flow
  journeys, including across every asynchronous hop, and identifies every record the journey produced.
- **SC-DEMO-006**: Across every sample flow, 0 responses contain another organisation's data, and a
  request scoped to one organisation returns nothing belonging to another on any path.
- **SC-DEMO-007**: A staff sample flow resolves its target organisation from durable platform state in
  100% of trials, and 0 flows accept a target organisation from a client-supplied value.
- **SC-DEMO-008**: A state change and its outbox message are durable together in 100% of trials; an
  induced failure between the two loses 0 messages and duplicates 0 effects.
- **SC-DEMO-009**: A message delivered more than once produces exactly 1 effect in 100% of trials.
- **SC-DEMO-010**: A sample flow reaches the same outcome whether or not a client is connected to
  receive its notification, in 100% of trials, and 0 notifications carry authority.
- **SC-DEMO-011**: The emitted API contract matches what each running service accepts for 100% of the
  operations it publishes, with 0 hand-maintained divergences.
- **SC-DEMO-012**: 0 sample flows produce an effect in any external system, modify any account,
  device or record, or are presented to any user as product capability.
- **SC-DEMO-013**: 0 of UC-01 through UC-12 are implemented, stood in for, or counted as complete by
  any sample flow.
- **SC-DEMO-014**: Where an operation requiring a human decision is encountered while the gate is
  unexercised, it is refused or routed to manual fallback in 100% of cases, and auto-approved in 0.

*Added 2026-09-18, proving the Integrations Service boundary.*

- **SC-DEMO-015**: RagCore reaches an external connector in **0** of 100% of attempts — verified by
  attempting the connection and observing it fail, and separately by attempting to resolve a
  connector credential and observing the secret store refuse it. 0 adapters, connectors or
  external-provider clients remain in RagCore.
- **SC-DEMO-016**: 100% of synchronous Integrations calls — catalogue reads and inert
  system-of-record operations — traverse the API gateway and authenticate as an application. 0 reach
  the service by another route, including 0 carrying a well-formed but self-supplied identity
  contract.
- **SC-DEMO-017**: 100% of tool executions travel as a message carrying only an opaque job
  identifier, correlation context and a routing kind. **0 carry** an organisation, actor, capability,
  target, parameters or credential.
- **SC-DEMO-018**: A duplicated execution command produces exactly **1** external effect in 100% of
  trials, and **each of the two idempotency boundaries is separately shown to be load-bearing** — the
  corresponding proof fails when that boundary alone is removed.
- **SC-DEMO-019**: A command carrying an out-of-contract organisation field is refused and
  dead-lettered in 100% of trials and processed in 0; and a command whose payload asserts a
  conflicting organisation produces an effect bound to the durable organisation in 100% of trials.
- **SC-DEMO-020**: RagCore's identity can resolve **0** connector credentials, and a scan of its
  source, configuration, environment and image finds 0 connector secrets.
- **SC-DEMO-021**: 100% of execution results are matched back to the work item that originated them,
  and one correlation identifier is recoverable across the gateway hop, both queues and all three
  deployables.
- **SC-DEMO-022**: The Integrations Service is identifiable as a distinct telemetry source for 100%
  of its invocations, emits attempt, outcome and duration metrics for 100% of connector calls, and
  its execution records are answerable without reading RagCore's telemetry.
- **SC-DEMO-023**: With the Integrations Service stopped, conversation, retrieval and guidance
  continue to succeed in 100% of trials, and a capability requiring an external effect falls back to
  manual resolution or escalation visibly in 100% of cases — 0 are reported to a user as completed.

#### Authorization

- **SC-AUTHZ-001**: An operation attempted by a person whose roles do not intersect the operation's accepted
  roles is denied in 100% of cases, with no instance of a role implying another.
- **SC-AUTHZ-002**: A person holding every staff role receives exactly end-user permissions on a customer
  surface, in 100% of trials, with no path by which any request they make promotes them to staff.

#### Identity and isolation

- **SC-IDENT-001**: 100% of approval and consent decisions are recorded against the identity of the person
  who made them, through an authenticated request. No decision is ever accepted from the notification
  channel or inferred from conversation text.
- **SC-IDENT-002**: Zero cross-organisation data exposure across the full authorization matrix — every role
  combination, every surface, every retrieval path — including deliberately adversarial attempts.

#### Surfaces and accessibility

- **SC-SURF-001**: A user can sign in and establish a working session on each of the three client surfaces.
- **SC-SURF-002**: All three client surfaces conform to WCAG 2.2 Level AA on every primary journey —
  sign-in, starting a session, receiving a streamed response, responding to a consent prompt, and
  working the approval queue — with zero Level A or Level AA failures outstanding at release.
- **SC-SURF-003**: Every primary journey can be completed using the keyboard alone, on all three surfaces.
- **SC-SURF-004**: Every primary journey presents a defined loading, empty and failure state, and no
  failure is ever shown as an empty result.

#### Conversation

- **SC-SESS-001**: 100% of submitted chat requests reach the agent flow and receive a response, a
  clarifying question, or an explicit handoff — never silence or an unexplained failure.
- **SC-SESS-002**: A response reaches the user progressively — partial output is observable before the
  response is complete — rather than appearing only when finished.
- **SC-SESS-003**: A user can record and then revise feedback on an agent response, with only the current
  signal counted, and no feedback signal alters any authorization, governance or retrieval outcome.
- **SC-SESS-004**: A session suspended past the retention window still holds the context it was
  suspended on, and a user returning to it can continue without repeating themselves.

#### Interruption and resume

- **SC-INTR-001**: Work suspended at any of the three interruption points survives indefinitely, and
  resumes correctly after at least 24 hours of suspension.

#### Execution integrity

- **SC-EXEC-001**: An approved action executes after the decision even when the requesting user's client has
  been closed since approval, in 100% of trials.
- **SC-EXEC-002**: A duplicate resume signal produces exactly one execution and exactly one external effect,
  in 100% of trials.

#### External systems

- **SC-EXT-001**: A third-party capability that has not been registered and entitled is not callable in
  100% of attempts, including when the third-party system actively advertises it.
- **SC-EXT-002**: A further third-party target system can be added by registering its capabilities and
  governance treatment alone, with no change to any authorization, approval or audit mechanism.

#### Manual fallback

- **SC-FALL-001**: 100% of requests that cannot be resolved fall back to human resolution with their
  context preserved, and no request is ever answered with a fabricated or unverifiable result.
- **SC-FALL-002**: 100% of escalated requests reach the queue in the system of record with their transcript,
  candidates and reason attached — including escalations raised while that system was unavailable,
  which replay rather than being lost.

#### Platform operation

- **SC-OPS-001**: A single user request can be followed end to end — across suspension, resume and
  asynchronous execution — using one correlation identifier, in 100% of traced journeys.
- **SC-OPS-002**: An organisation that exhausts its own budget is throttled, and a second
  organisation's requests are unaffected — verified deterministically by driving one organisation past
  its limit, without a load harness. Verification under real load concentration arrives with the scale
  envelope, which is not yet defined.

#### Audit and retention

- **SC-AUDIT-001**: Every consequential action produces a durable record naming requester, approver,
  executor, means, organisation and result — verifiable at 100% coverage.
- **SC-AUDIT-002**: Data past its retention window is removed for every class, verified independently per
  class, with no organisation retaining data indefinitely through missing configuration.
- **SC-AUDIT-003**: Removing expired chat content leaves the corresponding audit records intact and complete.

### Non-Binding Performance Targets

These are **good to have**, not acceptance criteria. Nothing in this section gates a release, blocks a
merge, or counts as a defect when unmet. They exist to give engineering a direction of travel, and
they are deliberately excluded from the Measurable Outcomes above.

The platform specification requires the response-latency objective to be re-baselined against a
measured hop count before any figure is committed. Until that measurement exists, committing to a
number would be guessing.

- **PT-001**: Sign-in to a usable session feels immediate on a normal connection.
- **PT-002**: The first part of a response appears quickly enough that the user does not wonder whether
  the request registered.
- **PT-003**: Streaming keeps pace with reading speed, so the user is not waiting between fragments.

A measured objective replaces this section once the re-baseline is done. At that point the figures
move into Measurable Outcomes and become binding — not before.

## Assumptions

- **The scaffold demonstrates the case boundary without a live instance.** ServiceNow as system of
  record is now stated as a requirement (FR-EXT-001 onward) rather than assumed. The scaffold exercises the
  adapter boundary and the queue-and-replay path; it does not require a provisioned instance to do so.
- **The customer portal is scaffolded, not shipped as product.** The platform specification defers the
  customer web portal beyond the initial release. It is included here as a working surface skeleton so
  the three-surface model is real, consistent with building a scaffold rather than a product.
- **Desktop script execution has nothing to execute in the scaffold.** The catalogue is empty until
  UC-01 through UC-12 are defined, so the surface and its safeguards exist but no script runs.
- **Approval routing is single-group in the initial release.** Tiered approval is a later policy
  change, not an architectural one, so `senior_technician` exists without any operation accepting it.
- **Knowledge sources are organisation-scoped only.** There is no shared or cross-organisation corpus,
  so no consent or withdrawal mechanism for pooled knowledge is needed.
- **Feedback applies to agent responses.** The source documents specify per-message feedback without
  restricting the message sender. Rating agent-authored messages is the reading adopted here, because
  the signal exists to evaluate the agent's response; rating one's own message carries no meaning.
- **Third-party target systems are named per organisation, not platform-wide.** OneLogin and Duo are
  the first examples; which organisations use which systems is configuration, and the scaffold
  demonstrates the boundary and its governance rather than any particular vendor integration.
- **Users have a modern browser or the supplied desktop application, and network connectivity at the
  moment of any device-side execution.** Offline operation is out of scope.
- **Notification delivery is best-effort.** Clients recover state by querying, so a missed notification
  delays awareness but never loses work or changes what is authorized.

## Dependencies

- **Product definition for UC-01 through UC-12.** Blocks any autonomous resolution. Until supplied,
  the platform triages and hands off but resolves nothing automatically.
  *Revisit when:* a product definition exists for any single use case — one is enough to unblock
  Stage 14 for that use case, and all twelve are not required together.
- **Enterprise identity, with staff role groups assigned.** Blocks all sign-in and all staff
  authorization testing.
  *Revisit when:* the `Synthia_Agents` and `Synthia_Admins` groups exist in the Operator tenant and
  the platform's application registration is consented. Until then the authorization matrix is
  provable only against fabricated role sets, never against real ones.
- **Endpoint execution safeguards.** Script distribution and integrity verification on the endpoint,
  script privilege level, and result attestation are named open items in the platform specification.
  They block the device-execution path from carrying anything beyond non-elevated, non-destructive
  operations.
- **The Integrations Service boundary's residual decisions.** ADR-0007 leaves two items open that
  this specification depends on: **which system-of-record operations are synchronous** (the platform
  specification classifies six write classes identically but makes only case creation clearly
  blocking), and **the exact result fields of the job record together with the permission scope that
  confines the Integrations Service to writing only those**. FR-INTEG-020 and FR-DEMO-025 are
  specified in full and are provable only once the second is settled, because the protection is
  enforced at the database permission boundary rather than in application code.
  *Revisit when:* both are recorded. Neither blocks the remaining Integrations demonstrations.
  *Revisit when:* ADR-0004's two residual items close — script signing, and the taxonomy of what
  makes a catalogue entry destructive. Both are prerequisites for lifting the §35.4 shipping gate,
  and neither is needed before Stage 14.
- **Second-approval behaviour.** One case carries at most one approval; what happens when a session
  needs a second consequential operation is an inherited open item and is currently assumed to
  escalate.
  *Revisit when:* the first use case requiring two consequential operations in one session is
  defined. The assumption holds until then and costs nothing, because each scaffold reference
  fixture needs exactly one.
- **A provisioned platform environment, edge included.** *Added 2026-09-16.* FR-DEMO-019 makes
  scaffold acceptance depend on a deployed public edge, web application firewall, API gateway and
  container platform, with identity configured at the gateway. Until that environment exists, the
  thirteen sample flows can be *written* and can pass against the deployables, but **none of them can
  be accepted** — SC-DEMO-001 is not satisfiable, and the scaffold is not complete.
  *Revisit when:* the environment is provisioned and the gateway derives identity. This is the
  longest-lead dependency in the scaffold and the one most likely to be discovered late, because
  every flow passes locally right up until the moment it has to cross a boundary that is not there.
- **Localization retrofit.** *Revisit when:* any customer requires a language other than English. English-only with hardcoded strings is a deliberate choice for the
  scaffold, with string externalization deferred rather than rejected. Adding a second language later
  will require retrofitting externalization across the surfaces already built; this cost is known and
  accepted, and is recorded here so it is not rediscovered as a surprise.
- **Residency retrofit.** Single-region is a deliberate choice, with per-organisation region recording
  deferred rather than rejected. If an organisation later requires its data held in a particular
  region, the region dimension must be added to the data model, the knowledge indexes and the
  deployment topology, and existing data migrated. This is materially harder than the localization
  retrofit above; the cost is known and accepted, and is recorded so it is not rediscovered later.
  *Revisit when:* any customer contract requires data held in a named region — the trigger is
  contractual, not technical, so it can arrive with no engineering warning.
- **Queue routing and field mapping.** The requirement that escalation reaches the ServiceNow queue is
  settled; *which* queue or assignment group, and how platform fields map onto the existing taxonomy,
  is an inherited open item in the source documents and MUST NOT be invented. Escalation routing is
  configuration per organisation until that mapping is supplied.
  *Revisit when:* the ServiceNow owner supplies the assignment-group mapping and field taxonomy for
  the first onboarded organisation. Escalation is buildable before then; only its destination is
  unresolved.
- **Responsiveness re-baseline.** No performance figure is committed. Responsiveness is recorded as
  non-binding targets (PT-001 to PT-003) and is explicitly good to have rather than an acceptance
  criterion. A measured re-baseline against actual hop count is required before any figure becomes
  binding, and until then a release MUST NOT be gated on one.
  *Revisit when:* the hop count on a representative grounded path has been measured.

## Out of Scope

**Out of scope for the scaffold, specified for the platform** *(added 2026-09-16)*. Each of the
following remains a requirement of this document and is not built now. Listing them here scopes the
build; it does not weaken the design, and FR-DEMO-017 says so normatively.

- `STAFF_APPROVAL` workflow behaviour — the treatment, the gate and the authority model stay specified.
- `END_USER_APPROVAL` workflow behaviour — consent remains a distinct authority, never inferable from
  chat text and never a substitute for staff approval.
- The approval user interface.
- The consent user interface.
- Real endpoint execution.
- Desktop script execution.

**Out of scope entirely**:

- Definitions or behaviour for UC-01 through UC-12. The reference operations are path fixtures and are
  explicitly not use cases.
- Autonomous resolution of any request, until those definitions exist.
- Runtime-generated scripts or open-ended agency.
- Cross-organisation knowledge pooling.
- Localization, translated content and locale negotiation. English only.
- Data residency, region pinning and data sovereignty. A single region serves all organisations.
- Any authorization or policy decision made on a client.
- Approval authority held in an external system.
- Remote interactive control of a customer device.
