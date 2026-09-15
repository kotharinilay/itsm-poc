# Specification Quality Checklist: Synthia Platform Engineering Scaffold

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-15
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

**Outstanding:**

- Two deferred structural items are recorded under Dependencies with their retrofit cost stated:
  string externalization for localization, and the per-organisation region attribute for residency.
  Both are accepted deferrals, not gaps.

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- The single open marker does not block `/speckit-plan` for the surrounding scope, but FR-INTR-005 itself
  cannot be planned until answered
