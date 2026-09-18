# 0008. Defer certificate-based gateway-to-backend provenance

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** Platform architecture owner
- **Supersedes:** nothing
- **Amends:** nothing
- **Related:** [0007](./0007-integration-service-boundary.md) (adds the third backend this hop served)

> **This record removes a security control and introduces no replacement.** That is the decision,
> not a side effect of one. `docs/adr/README.md` requires a record whenever a change "relaxes a
> security control the constitution states unconditionally"; this is such a change, and the
> consequence is stated in full under [Consequences](#consequences) rather than softened.

## Context and Problem Statement

`specs/001-platform-scaffold/spec.md` **FR-IDENT-012** requires that a service be able to
distinguish a header contract set by the gateway from one supplied by a caller, and refuse any
request on an audience path that cannot prove gateway provenance. It states explicitly that
**network placement alone MUST NOT be treated as that proof**.

The reason is structural. Identity is derived exactly once, at APIM, and stated to services in the
closed five-value `X-Idp-*` contract (FR-IDENT-011, specification §11.5). Backends consume that
contract as authoritative and never parse a token. For a service in that position, **reachability
is the ability to assert any organisation and any role**: anything that can open a connection can
name a tenant and a role set, and be believed.

Internal-only Container Apps ingress does not narrow that to APIM. It admits everything already
inside the environment — a compromised sidecar, a misconfigured job, a second container app, a
build agent with network line of sight.

### What was built to close it

A certificate-based mechanism, implemented across both stacks and all three deployables:

- APIM presented a client certificate on every backend connection, read from Key Vault as its own
  managed identity and referenced by `certificate-id`.
- Container Apps ingress ran `clientCertificateMode: require`, validated the certificate, and
  republished its SHA-256 hash as `X-Forwarded-Client-Cert` — set by ingress itself, so a caller
  could not forge it.
- `GatewayProvenanceMiddleware` (.NET) and `ragcore.api.middleware.provenance` (Python) compared
  that hash against a configured allow-list and **refused, rather than sanitised**, on mismatch.
- An empty allow-list failed the process at startup, so an unconfigured deployment could not serve.
- Rotation was a sequenced release; expiry was alerted at 45 days and paged at 30.

The mechanism worked and was tested. It is being deferred for reasons of **architecture sequencing,
not defect**: it carries a certificate lifecycle, an expiry, an order-sensitive rotation runbook and
a standing Azure identity exemption, and the platform is not yet ready to own those operationally.
That judgement is an architecture and security decision in its own right, and it has not yet been
taken deliberately.

## Decision Drivers

- The mechanism is the only Azure identity exemption in `build/policy/azure-identity.json`: it is
  the one credential in the platform with a lifecycle and an expiry rather than a managed identity.
- Its rotation is **order-sensitive and unforgiving** — widen the backend allow-list *before*
  repointing APIM, or every audience 403s while health probes stay green and replicas stay in
  rotation. That is a production outage with no deployment in the window to correlate against.
- Certificate expiry was the residual risk of the whole edge design, and its alerting existed
  solely to make the residual survivable.
- Container Apps may document Easy Auth for internal ingress, which would replace the certificate
  with a managed-identity token and remove the exemption entirely. Building the lifecycle now may
  be building the wrong thing.
- **No interim substitute is acceptable.** A shared secret, API key or bearer header in this
  position is a replayable credential that appears in every header-capturing log — strictly worse
  than the certificate and no better than nothing once an attacker has seen it once.

## Considered Options

1. **Keep the mechanism as built.** Rejected for this scaffold: it requires certificate issuance,
   an owned rotation procedure and expiry paging to be in place before it protects anything, and
   none of those are.
2. **Replace it with a shared secret or API key header.** Rejected. See Decision Drivers. It looks
   like a control and is a replayable bearer token; adopting it would make the platform's security
   posture *worse* while appearing to preserve it.
3. **Keep the middleware with an optional allow-list, disabled when unconfigured.** Rejected. This
   is the fail-open refactor the original code was explicitly shaped to prevent: "only enforce when
   configured" reads as caution and is an open door, and a disabled control still reads as an
   enabled one in review.
4. **Defer the mechanism in full, remove it from the active architecture, and record the gap.**
   Chosen.

## Decision Outcome

**Chosen: option 4.** The certificate-based gateway-to-backend provenance mechanism is **deferred**.
It is removed from the active architecture, from the implementation, from the deployed
configuration, from CI and from the test suites. **Nothing replaces it.**

### Explicitly deferred

| Item | Where it lived |
|---|---|
| APIM client certificate presented to backends | `build/infra/apim/global.inbound.xml`, `build/infra/apim/apis.json` |
| Ingress requiring the certificate | `clientCertificateMode: require` in `build/docker/containerapps/*.yaml` |
| The forwarded certificate header | `X-Forwarded-Client-Cert` |
| Backend certificate hash validation | `GatewayProvenanceMiddleware.cs`, `ragcore/.../provenance.py`, `integrations/.../provenance.py` |
| Certificate hash allow-list | `EdgeTrust__GatewayCertificateThumbprints`, `SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS`, `SYNTHIA_INTEGRATIONS_EDGE_TRUST__GATEWAY_CERTIFICATE_THUMBPRINTS` |
| Gateway client certificate in Key Vault, and the APIM certificate entity | `build/policy/edge-trust.json` `gatewayCertificate`, APIM `certificate-id` named value |
| The APIM identity's Key Vault role | `build/infra/identity/managed-identities.json` |
| Certificate lifecycle and rotation | `docs/runbooks/rotate-gateway-certificate.md` (removed) |
| Certificate expiry alerting | `build/infra/monitoring/gateway-certificate-expiry.json` (removed) |
| The Azure identity exemption this hop held | `build/policy/azure-identity.json` `containerapps-ingress` |
| Deployment and architecture guards enforcing the above | `check-edge-path.sh`, `verify-edge-guard.sh`, `EdgeTrustPolicyTests.cs`, `test_edge_trust_policy.py` |

### What remains active, unchanged

Front Door + WAF as the sole public edge. APIM as the API trust boundary and the single point of
identity derivation. **APIM's unconditional deletion of every inbound copy of the `X-Idp-*`
contract**, before validation, inbound and outbound. The closed five-header contract itself, and
every service-side rule about it: no token parsing, no self-asserted tenant or role, canonical role
ordering. The Front Door identifier check on the APIM origin. Internal-only Container Apps ingress
and the prohibition on external ingress. APIM routing and per-audience policies. Managed identity,
Azure RBAC and Key Vault for everything that still needs them. Tenant isolation, authorization,
correlation and trace propagation, Service Bus authentication, workload identity, OpenAPI contract
controls, audit, telemetry and container hardening.

**This deferral is not permission to expose a backend publicly.** `external: false` remains
mandatory on every application container app and is still guarded.

## Consequences

### The guarantee that is now absent

**A caller positioned inside the container apps environment can reach any backend directly, present
an `X-Idp-*` contract of its own choosing, and be believed.** It can name any tenant and any role
set. Tenant isolation, authorization and audit all sit *downstream* of that contract and will
faithfully enforce decisions made from a forged identity.

This must not be described as mitigated, compensated or defence-in-depth. FR-IDENT-012 exists
because network placement alone is not proof, and network placement alone is what this hop now has.

### What still holds, and its limit

APIM deletes every inbound copy of the contract before validation, so **a caller arriving from the
internet cannot smuggle one through the gateway**. Combined with internal-only ingress and no public
FQDN, the attack requires a foothold inside the environment. That is a real and meaningful barrier
and it is the whole of the barrier — it is a first step, not a second control.

### Consequences for the record

- **FR-IDENT-012 is marked DEFERRED** in `specs/001-platform-scaffold/spec.md` rather than deleted
  or quietly left as an unmet active requirement.
- **No acceptance criterion depends on this mechanism.** SC-DEMO-003b's backend-side half is
  retired with it.
- The `apim-to-backend` hop in `build/policy/edge-trust.json` is the only hop with a single control,
  and declares `applicationControlStatus: "deferred"` with a pointer to this record. A test asserts
  that any hop lacking an application control says so explicitly and names an existing ADR with no
  replacement — so a *second* hop cannot lose its application control silently.
- A test asserts no backend in `apis.json` declares any credential, so the gap cannot be filled
  informally with a secret or key.
- The platform now has **no Azure identity exemption at all**; managed identity is used everywhere
  it is supported, and a test asserts the exemption list is empty.

## Migration impact

None at runtime, because the mechanism was never provisioned: T233e (issue the certificate) and
T233f (set the allow-list) were both still open. No certificate was issued, no allow-list was ever
populated, and no deployed revision ever enforced the check.

Services that previously **refused to start** without an allow-list now start without one. This is
the intended change and is why the settings were removed rather than defaulted — a setting that is
read but optional is the fail-open shape this ADR rejects.

## Unresolved

**The decision this record defers is still owed.** Deferring is not answering.

| Item | Must be settled |
|---|---|
| How gateway-to-backend provenance is proved | Before the platform carries production customer data |
| Whether the answer is the client certificate, Container Apps Easy Auth on internal ingress, or something else | At the same time |
| Who owns certificate issuance, rotation and expiry paging, if the certificate returns | Before it returns, not after |

### Re-entry condition

This mechanism **must not return to the implementation backlog by default**. Before any
gateway-to-backend provenance mechanism — this one or another — is implemented:

1. this architecture/security decision is revisited and **explicitly approved**;
2. the approval names the operational owner of the credential's lifecycle;
3. this record is superseded by a new ADR. It is not amended in place, and its number is not reused.

Until then, any change that adds a backend credential, an ingress client-certificate requirement, a
provenance middleware or a trusted header on this hop is **out of scope by construction** and should
be refused in review with a pointer to this record.

## More Information

- `build/policy/edge-trust.json` — the single registry; the `apim-to-backend` hop records the
  deferral, and `backendRules.rejectSpoofedIdentity` records what is no longer enforced.
- `specs/001-platform-scaffold/spec.md` — FR-IDENT-012, marked DEFERRED.
- `specs/001-platform-scaffold/tasks.md` — T233a–T233f, retired `[D]` against this record.
- `Synthia-Platform-Specification.md` §10.3 — the network trust model, with the deferred hop noted.
