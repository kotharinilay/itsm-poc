# Integrations Service Contract

**Audience**: workload — app-only authorization. **The service is not client-facing.**

**Date**: 2026-09-18 | **Architecture**: `Synthia-Platform-Specification.md` §21.6,
[ADR-0007](../../../docs/adr/0007-integration-service-boundary.md)

The Integrations Service is a separate deployable parallel to RagCore. It owns the tool catalogue, the
connector registry and **all** traffic to external systems. This document is the behavioural contract;
the concrete OpenAPI document is emitted from the running service and validated against this by
contract tests.

## Routing

| Path prefix | Deployable | Audience | Nature |
|---|---|---|---|
| `/api/workload/v1/integrations/...` | **Integrations Service** | Workload | Catalogue read; synchronous system-of-record operations |
| `/api/workload/v1/...` | RagCore | Workload | Execution-leg operations |

**Longest matching path wins** — the same rule `apis.json` already proves with
`/api/customer/v1/views`. APIM resolves the most specific prefix first, so the two APIs coexist under
one prefix with no ordering flag to get wrong.

Both share `build/infra/apim/workload.v1.xml`. Identity is derived per **audience**, not per
deployable; two policies would be two places for the derivation to drift.

## Authentication

| Property | Rule |
|---|---|
| Credential class | **App-only.** A delegated token is refused with 403 — `scp` is present only on a delegated token, and there is no safe interpretation of a human credential on this surface |
| Application role | **Its own**, distinct from the generic workload role, so a workload-audience caller cannot drive connectors merely by being one |
| Token parsing | **The service MUST NOT parse a token.** It consumes only the closed `X-Idp-*` contract APIM emits |
| Caller-supplied identity | **Never trusted.** APIM deletes every inbound copy of the contract and writes its own; a request arriving with a self-supplied one is refused, not sanitised |
| Backend authentication | Mutual TLS from APIM, the same certificate and the same recorded exemption as the other two backends |

## The organisation is never a parameter

**This is the rule that shapes every endpoint below.** A workload token's `tid` is the *Operator*
tenant and is never the customer organisation. So:

- No endpoint accepts an organisation, role or audience parameter.
- Every request carries an **opaque identifier** — a session, work item or job — and the service
  resolves the organisation from the durable object that identifier names.
- A request that named an organisation directly would be a caller asserting authority the platform
  derives, which constitution Principle I forbids outright.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/workload/v1/integrations/catalogue?sessionId=` or `?workItemId=` | The capability set entitled to the organisation that durable object belongs to |
| `POST` | `/api/workload/v1/integrations/case-operations` | Synchronous system-of-record operation, bound to an opaque identifier |
| `GET` | `/api/workload/v1/integrations/health` | Liveness for the service |

**There is deliberately no execution endpoint.** Normal tool execution is a Service Bus command
(`FR-INTEG-013`); a synchronous execution route would be a second, ungoverned path to the same effect.

### Catalogue response

```json
{
  "items": [
    {
      "catalogueId": "reference.inert_read",
      "catalogueVersion": 1,
      "kind": "read",
      "entitled": true,
      "available": true
    }
  ],
  "nextCursor": null
}
```

`entitled` and `available` are **separate fields on purpose**: `FR-EXT-022` requires *entitled but
unreachable* to be distinguishable from *not entitled*, because they need different operator actions
and neither may be presented to a user as a failure of their request.

The response carries **no treatment, no accepted roles and no risk tier**. Those live in the
governance record in RagCore, and a catalogue response that carried them would invite a caller to
decide from them.

## Which operations are synchronous — **open**

`Synthia-Platform-Specification.md` §22.3 lists six system-of-record write classes and classifies all
of them `AUTO`; §22.5 makes only case creation clearly blocking, since a session that cannot commit a
case cannot enter Resolution Mode. **Whether the other five are synchronous or asynchronous is
recorded as unresolved in ADR-0007 and must be settled before this contract is frozen.** The endpoint
above is shaped for case creation; the rest are not yet specified here rather than being guessed.

## Conventions

Inherited without exception from [README.md](./README.md): URI-segment versioning; camelCase JSON both
directions; RFC 9457 `application/problem+json` with `correlationId`; `X-Correlation-Id` accepted,
generated when absent and echoed; keyset pagination with opaque cursors; allow-listed filter and sort
fields; `Idempotency-Key` accepted on any state-changing endpoint; 401 unauthenticated, 403
unauthorized, 404 where existence is itself organisation-scoped information.

## Health

| Endpoint | Covers |
|---|---|
| `/health/live` | Process only. **No dependency checks** |
| `/health/ready` | Durable store, message transport, secret store |

**Readiness MUST NOT depend on any external customer system.** A ServiceNow or Graph outage is an
operational condition to be reported, not an unready replica — a readiness probe that failed on it
would remove capacity precisely when the fallback path needs it.

## Contract emission

Emitted from the running service to `build/contracts/integrations/workload.v1.openapi.json`, through
the same five gates as every other document: generation, determinism, publishability, compatibility,
freshness.

**One document per audience per deployable.** RagCore and the Integrations Service both serve the
workload audience and each emits its own document; the compatibility gate therefore diffs **per
deployable**, not per audience. A merged document is prohibited.

`tenantId` is forbidden as a parameter or request field here, as everywhere. It is permitted in a
response only where it reports the organisation a row already visible to the caller belongs to.

## Rules that outrank any endpoint definition

1. No endpoint accepts an organisation, role or audience parameter and trusts it.
2. The service performs **no tool-selection reasoning**. It executes the capability it is instructed
   to execute and chooses nothing.
3. It assigns **no execution treatment** and performs **no role intersection**.
4. It re-verifies every authority **fact** at execution time against durable state, even where the
   caller already retrieved the catalogue. Prior retrieval is not standing permission.
5. It reaches no model provider and no AI Gateway. It does no reasoning.
6. **No direct route to it exists.** Every call traverses Front Door, the WAF and APIM — including one
   carrying a well-formed but self-supplied identity contract, which is the shape a bypass takes.
