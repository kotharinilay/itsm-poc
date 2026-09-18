# Specification Quality Checklist: Synthia Platform Engineering Scaffold

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-15 | **Last validated**: 2026-09-16 (contradiction review of the revised scope)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Validation Notes

**Iteration 1 — issues found and corrected:**

1. *Implementation detail leak.* Early drafting named specific runtime components and stores
   (RagCore, the durable store, the message transport) in requirements. Rewritten to behavioural
   language: "deterministic governance", "durable suspension", "an authenticated request",
   "the notification channel". Component and technology choices are left to `/speckit-plan`.
2. *Untestable success criteria.* Initial criteria restated the feature description
   ("graph can resume"). Rewritten with observable thresholds and trial-based phrasing —
   SC-INTR-001 (24-hour suspension), SC-EXEC-001 (client closed, 100% of trials), SC-EXEC-002 (duplicate signal,
   exactly one effect).
3. *Missing negative coverage.* Added scenarios for the cases where the product's guarantees are
   most likely to break silently: affirmative chat text not counting as consent (US3-2), consent not
   satisfying approval (US3-5), `administrator` unable to approve (US2-7), and empty-intersection
   denial (US5-4).
4. *Scaffold honesty.* Added SC-SCOPE-001 and FR-INTR-011 to state plainly that with no use case defined, 100%
   of action-requiring requests route to manual resolution. This is the expected outcome of the
   scaffold, not a defect, and the spec says so rather than implying resolution capability it does
   not have.

**Iteration 2 — surface/persona rule added:**

5. *Missing persona-by-surface rule.* The spec defined the two persona classes but never stated that
   the surface determines which applies. Added FR-SURF-001 through FR-SURF-005, US5 scenarios 7-8, three edge
   cases and SC-AUTHZ-002: a person on a customer surface is an end user regardless of staff roles held,
   the staff portal cannot originate a session, and take-over is participation rather than
   origination. Sourced from the platform specification, not invented. The same rule was added to
   constitution Principle II (v2.5.0), since "a user cannot promote themselves" is a security
   invariant rather than a surface detail.

**Iteration 3 — third-party integration resolved:**

6. *FR-INTR-005 marker closed.* Answered as option A: OneLogin and Duo are third-party target systems the
   agent reads details from or performs operations against, reached as MCP servers. Two details from
   the answer changed the requirement's shape rather than just filling a blank: the systems are
   **examples, not a closed list**, and MCP is the mechanism. Rewritten as an extensibility
   requirement (FR-INTR-005 to FR-EXEC-004) covering read/action tagging, discovery-is-not-entitlement,
   per-organisation entitlement and credentials, third-party output as data, and the rule that adding
   a system requires registration alone. No divergence from the platform specification: section 21.2
   already states that MCP-discovered tools inherit the same governance, and section 21.4 already
   anticipates per-tenant credentials for arbitrary customer systems.

**Iteration 4 — performance figures demoted to non-binding:**

7. *Timing removed from acceptance criteria.* SC-SURF-001 and SC-SESS-002 carried latency figures (30s sign-in,
   3s first output) that were never committed. Per direction, performance is good to have, not an
   acceptance criterion. The figures were removed from Measurable Outcomes and restated as PT-001 to
   PT-003 in a clearly separated Non-Binding Performance Targets section that gates nothing.

   The binding behaviour in both criteria was preserved rather than deleted with the numbers: SC-SURF-001
   still requires a working session on all three surfaces, and SC-SESS-002 still requires progressive
   delivery — restated as "partial output observable before the response is complete", which is
   verifiable without any time commitment. Dropping SC-SESS-002 outright would have silently lost the
   streaming guarantee behind FR-SURF-002.

**Iteration 5 — clarification session 2026-09-15:**

8. *Five clarifications integrated.* Accessibility (WCAG 2.2 AA, all three surfaces), language
   (English only, externalization deferred), retention (class-based defaults: chat 90d, audit 7y,
   working state 30d), residency (single region, region attribute deferred), and reference operations.

9. *Internal contradiction found and fixed.* The Overview claimed the scaffold "demonstrates every
   load-bearing behaviour end to end", but User Stories 2, 3 and 4 each require the agent to propose
   an operation, and the catalogue was empty until UC definitions arrive — so those acceptance
   scenarios were unrunnable as written. Resolved by adding inert, labelled, production-excluded
   reference operations, one per execution treatment. The Independent Test lines for US2 and US3 now
   name the fixture that drives them, making them executable.

**Iteration 6 — scaffold scope correction (2026-09-16):**

10. *The scaffold demonstration requirement was corrected, and only that.* The scaffold no longer
    has to implement business approval semantics or a real approval/consent workflow. It proves
    platform infrastructure instead, through thirteen inert sample flows: the three API audiences,
    service-to-service, persistence, transactional outbox, publish/consume, notification,
    correlation propagation, organisation propagation, managed-identity authentication, secret
    binding and contract emission. Added as FR-DEMO-001 through FR-DEMO-018, User Story 6, and
    SC-DEMO-001 through SC-DEMO-014. The scaffold is complete when the SC-DEMO group is met.

11. *Nothing architectural was removed, and two requirements now say so normatively.* The identity
    requirements, tenant isolation, the authorization model, the governance architecture, the four
    execution treatments, PostgreSQL authority, ServiceNow as system of record, the derived retrieval
    index, transient cache, model egress, managed identity, secret store, contract emission, the
    gateway and edge, the container platform, the message transport, the notification channel and
    the three API audiences are all unchanged. FR-DEMO-017 states that the deferral is of a
    demonstration rather than of a design; FR-DEMO-018 states that an unexercised gate fails closed,
    so "not yet built" can never be implemented as "allowed by default". Without that second rule
    the correction would have been a silent permission grant.

12. *Item 9 above resolved differently, and better.* Iteration 5 recorded a contradiction between the
    Overview's claim to demonstrate "every load-bearing behaviour end to end" and an empty catalogue,
    and resolved it by adding reference operations to make the approval and consent stories runnable.
    That claim is now withdrawn: the Overview says the scaffold proves load-bearing *infrastructure*,
    and the approval and consent stories carry an explicit scaffold-scope banner marking them
    platform behaviour rather than scaffold acceptance. The reference operations remain and are still
    required — the sample flows need something inert to act upon (FR-SCOPE-004, amended).

13. *Two requirements were amended rather than replaced, each carrying its own amendment note.*
    FR-SCOPE-004 no longer requires the consent and approval paths to be demonstrable end to end;
    SC-SCOPE-002 no longer requires each treatment to be demonstrated through its workflow, and now
    measures what remains verifiable — that the catalogue carries all four and that classification is
    deterministic. Both notes name the date and the superseding requirement, so a reader who knew the
    old wording can see what changed and why.

**Iteration 7 — contradiction review of the revised scope (2026-09-16):**

14. *One genuine contradiction found and closed.* FR-DEMO-004 as first written required "a
    service-to-service flow between the two deployables" — a direct route, which `plan.md` forbids
    ("§13.4's no-direct-service-to-service rule holds between the two deployables"; "they meet only
    at PostgreSQL (versioned views) and Service Bus (opaque triggers)"). The traceability table
    contradicted the requirement text in the same document, which is how the defect surfaced.
    Resolved by clarification: service-to-service takes two permitted forms — asynchronous, over the
    message transport and published views; and synchronous, through the workload audience — and
    **neither is a direct call**. FR-DEMO-004 rewritten to require both forms; FR-DEMO-004a added to
    prohibit any route that bypasses the gateway; SC-DEMO-003a makes the prohibition measurable by
    requiring that a bypass be *attempted and observed to fail*, not merely unused.

15. *Edge and gateway traversal is now acceptance, not configuration.* FR-DEMO-019 requires every
    sample flow to be driven through the deployed public edge, web application firewall, API gateway
    and container platform. SC-DEMO-001 restated accordingly, and SC-DEMO-003b added: a request
    presented directly to a deployable must fail, **including one carrying a well-formed but
    self-supplied gateway header contract** — the shape a real bypass takes, and the one a naive
    negative test misses.

    > **Amended 2026-09-18.** SC-DEMO-003b is **DEFERRED** — see
    > [ADR-0008](../../../docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md).
    > The self-supplied-contract case no longer fails, because the control that refused it is
    > deferred and unreplaced. The rest of this item stands: FR-DEMO-019 and SC-DEMO-001 are
    > unchanged, and a direct request carrying no contract must still fail.

16. *The cost of that decision is recorded as a dependency rather than left to be discovered.* A
    provisioned platform environment including the edge is now the longest-lead dependency in the
    scaffold: the thirteen flows can be written and can pass against the deployables, but none can be
    *accepted* until the environment exists. Stated in Dependencies with the reason it tends to be
    found late.

**Known and accepted exception — Content Quality item 1:**

- *"No implementation details" is knowingly relaxed in one place.* The FR-DEMO preamble carries a
  traceability table naming the technology each flow resolves to (PostgreSQL, Service Bus, SignalR,
  Key Vault, Entra managed identity, OpenAPI). The requirements themselves stay in capability
  language — "the authoritative durable store", "the message transport", "the secret store" — and the
  table exists solely so a reviewer can check the scaffold against the component list without
  inferring the mapping. Recorded as a deliberate exception rather than ticked silently. Note that
  the spec already named ServiceNow, PostgreSQL and the transient cache before this change, as
  external-system constraints rather than design choices.

**Outstanding:**

- Two deferred structural items are recorded under Dependencies with their retrofit cost stated:
  string externalization for localization, and the per-organisation region attribute for residency.
  Both are accepted deferrals, not gaps.

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- The single open marker does not block `/speckit-plan` for the surrounding scope, but FR-INTR-005 itself
  cannot be planned until answered
