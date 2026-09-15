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

This specification defines the **initial engineering scaffold**: a real, working product skeleton that
demonstrates every load-bearing behaviour of the platform end to end, while containing **no resolved
use cases**. The twelve use cases of the initial product release are represented as placeholders
UC-01 through UC-12 and are awaiting product definition. Until they are defined, every request falls
back to manual resolution.

**Why build the skeleton before the use cases**: the risky parts of this product are not the use
cases — they are identity, organisation isolation, deterministic authorization, durable suspension around a
human decision, and honest reporting of what actually happened. Those must be proven first, because
every use case is built on top of them and none of them can be retrofitted safely.

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
  catalogue — one for each execution treatment — so that the governance, consent and approval paths
  are demonstrable end to end before any use case exists.
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
- **SC-SCOPE-002**: Each of the four execution treatments can be demonstrated end to end in a running
  scaffold using the reference operations, with no real effect occurring in any external system.
- **SC-SCOPE-003**: No reference operation is present in a production configuration, and none is ever
  presented to a user as a product capability.

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
  *Revisit when:* ADR-0004's two residual items close — script signing, and the taxonomy of what
  makes a catalogue entry destructive. Both are prerequisites for lifting the §35.4 shipping gate,
  and neither is needed before Stage 14.
- **Second-approval behaviour.** One case carries at most one approval; what happens when a session
  needs a second consequential operation is an inherited open item and is currently assumed to
  escalate.
  *Revisit when:* the first use case requiring two consequential operations in one session is
  defined. The assumption holds until then and costs nothing, because each scaffold reference
  fixture needs exactly one.
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
