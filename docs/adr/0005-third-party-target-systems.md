# 0005. Third-party target systems: OneLogin, Duo and the extensible set

- **Status:** Accepted
- **Date:** 2026-09-15
- **Deciders:** Platform architecture owner
- **Related:** [0001 — RagCore owns orchestration and execution](0001-ragcore-owns-orchestration-dotnet-owns-read.md)

## Context and Problem Statement

`Synthia-Platform-Specification.md` is the authoritative product and architecture source. **OneLogin and
Duo appear in it zero times.** They were introduced as a platform requirement outside that document,
which means every artefact referencing them currently rests on no authoritative basis — exactly the
condition that constitution Principle X exists to catch.

Their role was settled by direct decision: they are **third-party target systems** the agent reads
details from or performs operations against, driven by an incident — not identity providers, and not
verification steps. They are **examples, not a closed list**; further systems are expected.

This ADR records that decision so the divergence is traceable rather than implicit.

## Decision Drivers

- The authoritative specification cannot be silently extended (Principle X).
- Reading them as identity providers would conflict with Principle I, which makes enterprise identity
  the sole source of human identity.
- The set is open, so the architecture must absorb a new system without structural change.
- §21.2 already governs MCP-discovered tools; nothing new is needed to accommodate them.

## Considered Options

1. **Identity providers alongside Entra.** Rejected — conflicts with Principle I and would reopen the
   identity model.
2. **Verification steps inside a workflow.** Rejected — not what was decided, and would place them on
   the governance path rather than the action path.
3. **Third-party target systems reached as MCP servers.** Accepted.

## Decision Outcome

**Option 3.** OneLogin and Duo are third-party target systems, reached as **MCP servers** behind ports
declared in `application/` with adapters in `integrations/`. They are the first two members of an
open set.

No new architecture is required to support them, and that is the point:

- §21.2 already states that MCP-discovered tools inherit exactly the same governance as native ones,
  and that **discovery is not entitlement** — a tool appearing on an MCP server does not become
  callable.
- §21.4's credential table already anticipates arbitrary third parties: *"Other customer systems — per
  tenant and per system."*
- Every capability is `read` or `action`; an `action` never reaches the agent loop directly.

Adding a further system requires **registration in the governance catalogue and entitlement to an
organisation** — never a new authorization mechanism, approval path, or exception (spec `FR-EXT-010`,
`SC-EXT-002`).

### Divergence recorded

| Authoritative position | This decision |
|---|---|
| OneLogin and Duo are not mentioned | They are sanctioned third-party target systems |
| §21.3 names two adapters: ServiceNow and Microsoft Graph | The adapter set is open; ServiceNow and Graph remain the only ones with dedicated bounded contexts |

**No bounded context is added.** These systems are reached through the Tool Execution path and the
integration boundary; they do not become contexts of their own, and §14.1's eleven are unchanged.

## Consequences

**Positive.** The divergence is visible and traceable. The governance, entitlement and credential model
absorbs the addition without change, which is itself evidence the boundary was drawn correctly.

**Negative / accepted.**

- Each third party is another external dependency with its own availability, contract and rate limits.
- Provider-specific behaviour must be kept behind its adapter; the architecture test asserting no
  provider type reaches `domain/` or `application/` becomes more load-bearing with each addition.
- The authoritative specification does not describe these systems, so their operational detail has no
  upstream reference. If they become central rather than incidental, the platform specification should
  be amended rather than this ADR extended.

## Unresolved

- Which organisations use which systems is configuration and is not yet defined.
- Whether either system's operations appear among UC-01 through UC-12 cannot be known until those use
  cases are supplied.

## More Information

- `Synthia-Platform-Specification.md` §21.1–§21.5 (tool, MCP and external integration architecture).
- Constitution Principles I, III, VI and X; spec `FR-EXT-009` through `FR-EXT-018`.
