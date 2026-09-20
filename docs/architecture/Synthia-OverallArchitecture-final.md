# Synoptek ITSM Command Center (Synthia)

**Agentic ITSM Platform — Solution Architecture & Guiding Principles**

| | |
|---|---|
| **Status** | Alpha strategy — for architecture review board |
| **Aligned** | 15 September 2026 — reconciled against the Platform Functional & Architecture Specification |
| **Scope** | Logical + deployment reference architecture, principles, and cross-cutting design |
| **Date** | 27 August 2026 |
| **Created By** | Gitesh Tripathi |
| **Classification** | Confidential — Synoptek |

---

## Contents

- [1. Purpose, Scope & Audience](#1-purpose-scope-audience)
- [2. Architecture Drivers & Quality Attributes](#2-architecture-drivers-quality-attributes)
   - [2.1 Business drivers](#21-business-drivers)
   - [2.2 Key constraints](#22-key-constraints)
   - [2.3 Quality attributes & target SLOs](#23-quality-attributes-target-slos)
- [3. Architecture Principles](#3-architecture-principles)
   - [P01 — Gateway-mediated access, no direct paths](#p01-gateway-mediated-access-no-direct-paths)
   - [P02 — Two identity planes, strictly separated](#p02-two-identity-planes-strictly-separated)
   - [P03 — Tenant isolation is a first-class invariant](#p03-tenant-isolation-is-a-first-class-invariant)
   - [P04 — Bidirectional AI safety by default](#p04-bidirectional-ai-safety-by-default)
   - [P05 — Human-in-the-loop for consequential actions](#p05-human-in-the-loop-for-consequential-actions)
   - [P06 — Provider-abstracted, model-agnostic AI](#p06-provider-abstracted-model-agnostic-ai)
   - [P07 — Retrieval-grounded answers over free generation](#p07-retrieval-grounded-answers-over-free-generation)
   - [P08 — Stateless compute, externalised state](#p08-stateless-compute-externalised-state)
   - [P09 — Least privilege and secretless-where-possible](#p09-least-privilege-and-secretless-where-possible)
   - [P10 — Observability is built in, not added on](#p10-observability-is-built-in-not-added-on)
   - [P11 — Integrations are adapters, not leaks](#p11-integrations-are-adapters-not-leaks)
   - [P12 — Immutable, pipeline-delivered artifacts](#p12-immutable-pipeline-delivered-artifacts)
   - [P13 — Thin client, deep server](#p13-thin-client-deep-server)
   - [P14 — Evolvable by contract (alpha strategy)](#p14-evolvable-by-contract-alpha-strategy)
   - [P15 — Data sovereignty honoured per tenant](#p15-data-sovereignty-honoured-per-tenant)
   - [P16 — Cost is a design constraint (FinOps)](#p16-cost-is-a-design-constraint-finops)
- [4. Logical Architecture](#4-logical-architecture)
   - [4.1 Zone intent](#41-zone-intent)
- [5. Component Inventory](#5-component-inventory)
- [6. Security Architecture](#6-security-architecture)
   - [6.1 Identity & token flow](#61-identity-token-flow)
   - [6.2 Network segmentation & zero-trust](#62-network-segmentation-zero-trust)
   - [6.3 Secrets & data protection](#63-secrets-data-protection)
   - [6.4 Agentic threat considerations](#64-agentic-threat-considerations)
- [7. Multi-Tenancy Model](#7-multi-tenancy-model)
- [8. Data Architecture](#8-data-architecture)
   - [8.1 Stores & purpose](#81-stores-purpose)
   - [8.2 Retrieval store & ingestion](#82-retrieval-store-ingestion)
   - [8.2 Retrieval store & ingestion](#82-retrieval-store-ingestion)
   - [8.3 Classification, residency & lifecycle](#83-classification-residency-lifecycle)
- [9. AI & Agentic Architecture](#9-ai-agentic-architecture)
   - [9.1 Architecture-level responsibilities](#91-architecture-level-responsibilities)
- [10. Integration Architecture](#10-integration-architecture)
- [11. Key Interaction Flows](#11-key-interaction-flows)
   - [11.1 Problem-management flow (Synthia-triggered)](#111-problem-management-flow-synthia-triggered)
   - [11.1 Problem-management flow (Synthia-triggered)](#111-problem-management-flow-synthia-triggered)
   - [11.2 Elevated-approval branch (HITL)](#112-elevated-approval-branch-hitl)
   - [11.2 Elevated-approval branch (HITL)](#112-elevated-approval-branch-hitl)
   - [11.3 Knowledge ingestion](#113-knowledge-ingestion)
   - [11.4 Build & deploy](#114-build-deploy)
- [12. Deployment & Network Topology](#12-deployment-network-topology)
- [13. DevOps & Delivery](#13-devops-delivery)
- [14. Resilience, DR & BCP](#14-resilience-dr-bcp)
   - [14.1 Degradation modes](#141-degradation-modes)
- [15. Observability & Operations](#15-observability-operations)
- [16. Cost Governance (FinOps)](#16-cost-governance-finops)
- [17. Compliance, Audit & Governance](#17-compliance-audit-governance)
- [18. Cross-Cutting Traceability Matrix](#18-cross-cutting-traceability-matrix)
- [19. Risk Register](#19-risk-register)
- [Appendix A — Azure Deployment Architecture: Diagram & Trade-offs](#appendix-a-azure-deployment-architecture-diagram-trade-offs)
   - [A.1 Deployment walkthrough](#a1-deployment-walkthrough)
   - [A.2 Strengths (pros)](#a2-strengths-pros)
   - [A.3 Trade-offs & risks (cons) with mitigations](#a3-trade-offs-risks-cons-with-mitigations)
   - [A.4 How Does Overall Assessment Look?](#a4-how-does-overall-assessment-look)

---


## 1. Purpose, Scope & Audience

This document defines the reference architecture and governing principles for the **Synoptek Command
Center (Synthia)**, a multi-tenant, agentic ITSM platform that delivers AI-assisted service operations to
customer users and Synoptek staff. It captures the logical structure, the deployment/network topology,
the design intent per zone, and the principles that constrain future change so the platform evolves
coherently across tenants and teams.

**Audience:** the architecture review board, engineering leads, security and compliance reviewers, and
platform operations. Principles (§3) are normative — a conflicting design is corrected or the principle is
formally amended, never silently overridden. Physical sizing (SKUs, CIDRs, quotas) belongs in detailed
design and IaC and is out of scope except where it constrains the architecture.

## 2. Architecture Drivers & Quality Attributes

### 2.1 Business drivers

- Deliver AI-assisted incident handling and knowledge grounding to multiple customer tenants from a
  single platform.
- Preserve ServiceNow as the authoritative system of record while adding an agentic assist/orchestration
  layer above it.
- Keep Synoptek staff (technicians/admins) and customer users on strictly separate identity and
  authorization planes.
- Ship fast at alpha maturity without foreclosing a clean path to GA and additional tenants.

### 2.2 Key constraints

- Endpoints run inside customer networks; sensitive logic and data must not live on the endpoint.
- Model capability, price and availability change rapidly — no hard coupling to a single provider.
- Per-tenant data residency, retention and PII obligations differ and must be honoured individually.
- Agentic actions can be consequential; state-changing operations require human accountability.

### 2.3 Quality attributes & target SLOs

The architecture is optimised against the following attributes. These are the committed platform
defaults (per-tenant tunable where a contract requires it).

| Quality attribute | Target / SLO (initial) | Primary mechanism |
|---|---|---|
| Availability (platform APIs) | 99.9% monthly for APIM + control plane | Stateless compute, health-probed autoscale, zonal redundancy |
| Assisted-response latency | P95 < 4 s grounded; < 1.5 s cached — **to be re-baselined** against the gateway-mediated hop count (P01) | Semantic cache, streaming, retrieval tuning |
| Tenant isolation | Zero cross-tenant data exposure | `tid` enforced at every tier; namespaced stores/indexes |
| Security posture | Zero-trust; no standing secrets | Managed identity + RBAC, private endpoints, Key Vault |
| Scalability | Linear in nature | Independent horizontal scaling per service |
| Recoverability | RPO ≤ 15 min, RTO ≤ 1 h (control plane) | PITR on Postgres, IaC redeploy, ACR image pull |
| Auditability | 100% of consequential actions logged | Correlation IDs, approvals audit, guardrail logs |
| Cost efficiency | Token + cache budget | Provider-normalised metering, cache ROI tracking |

> **Reviewer note (assisted-response latency):** "Business to Decide this KPI."

## 3. Architecture Principles

Each principle is a rule, justified, and made actionable through explicit implications. Principle IDs
are referenced throughout and in the traceability matrix (§18).

### P01 — Gateway-mediated access, no direct paths
**Statement.** Every request reaches a protected capability only through a gateway: client/service
traffic via Azure APIM, and all model/agent/tool traffic via the Azure AI Gateway. Backend services are
never client-addressable.
**Rationale.** A single policy-bearing ingress is where AuthN/Z, throttling, quota, semantic caching and
observability are enforced consistently; point-to-point paths erode these controls and make isolation
unverifiable.
**Implications.**
- Synthia holds only the APIM endpoint; Container Apps ingress is internal-only.
- GenAI concerns (metering, caching, routing, safety) live at the AI Gateway, not in callers. The AI
  Gateway is a model/tool egress policy function and is **not** an identity boundary; it never
  establishes tenant, principal, approval or execution authority.
- Every application API call — client-to-service, service-to-service and Workload-to-service — traverses
  the public edge and APIM. There is no direct peer-to-peer application route.
- New capability = a published API product, not a new network route.

### P02 — Two identity planes, strictly separated
**Statement.** Customer users and Synoptek staff are separate authorization audiences and surfaces. Human identity, tenant binding, persona derivation and authorization are governed by the **Identity Plane**.

**Architecture implications.**
- The platform exposes distinct Customer, Staff and Workload API audiences.
- The Gateway consumes validated identity and routes according to the Identity Plane contract.
- A Synoptek employee using a customer surface is an end user for that request.
- No component may create a second or competing identity authority.

**Authority.** The detailed authentication, tenant, role, Workload and authority-propagation rules are defined only in `identity-plane.md`.

### P03 — Tenant isolation is a first-class invariant
**Statement.** Every request, cache entry, index partition, data row and log record carries a verified
tenant identifier derived from the validated token at APIM. **Tenant status is not held at APIM**: tenant
admission is a fail-closed service-side check against the PostgreSQL tenant registry.
**Rationale.** Multi-tenancy without enforced isolation is the largest blast-radius risk; a single edge
check fails the moment an internal component is compromised.
**Implications.**
- `tid` derived from the validated token at APIM and re-checked at RagCore and the data tier. Tenant
  *status* (active / suspended / offboarded) is authoritative in PostgreSQL and checked service-side; a
  service-side cache is permitted only if bounded and fail-closed.
- Redis keys, Postgres access and the AI Search SOP index are isolated with a `TenantID` column at least
  in the Alpha stage; the shared ServiceNow SoR is separated by tenant-field row-level ACLs.
- Semantic-cache hits are tenant-scoped to prevent bleed-through.

> **Reviewer note (P03):** "To be confirmed with SNOW and Business if this holds good."

### P04 — Bidirectional AI safety by default
**Statement.** All model interactions pass through guardrails on both the inbound (prompt) and outbound
(completion) path; unsafe or non-compliant content is blocked or remediated.
**Rationale.** Agentic systems act on input and produce content that drives operations; one-sided safety
leaves either prompt-injection or unsafe-output exposure open.
**Implications.**
- Azure AI Content Safety is invoked on request and response — not optional per call.
- Retrieved and tool/MCP content is treated as untrusted data, never as instructions.
- Guardrail decisions are logged with correlation IDs for audit and false-positive tuning.

### P05 — Human-in-the-loop for consequential actions
**Statement.** Any agent-initiated action with material or irreversible effect (write-backs, approvals,
privileged changes) is routed through the supervised Approvals service and needs an authorised human
decision before execution.
**Rationale.** Autonomy is valuable for retrieval and drafting but unacceptable for state change without
oversight; a real-time approval surface keeps a human accountable while preserving speed.
**Implications.**
- RagCore's LangGraph flow raises a human-in-the-loop interrupt; the Approvals service records the
  request and notifies staff in real time (Azure SignalR). The **verdict is submitted through an
  authenticated Staff API request with a fresh staff token** — SignalR delivers the notification and the
  result, never the authorization. PostgreSQL holds the authoritative approval record and it is mirrored
  to ServiceNow.
- The classify node decides self-service vs. elevated-approval vs. not-allowed; only self-service or
  approved actions proceed.
- Approval policy is based on per-action-class, and auditable.

### P06 — Provider-abstracted, model-agnostic AI
**Statement.** Consumers depend on the AI Gateway abstraction, not a specific model/vendor; Azure OpenAI
and Foundry-hosted agents (incl. Anthropic Claude via Foundry) are pluggable behind a stable contract
exposed via the APIM endpoint and consumed by internal services only.
**Rationale.** Model capability/price/availability change fast; coupling business logic to one provider
makes optimisation and failover a rewrite.
**Implications.**
- Prompting, caching and routing sit behind the gateway; swapping/A-B-testing models does not touch
  Command Center code.
- Token metering is provider-normalised so spend is comparable.

### P07 — Retrieval-grounded answers over free generation
**Statement.** Operational answers are grounded via RagCore on knowledge and incident indexes segregated
by customer/tenant id (historic incident resolutions), plus live state, rather than model parametric
memory alone.
**Rationale.** ITSM correctness depends on current tenant-specific facts; ungrounded generation is
plausible but unaccountable, grounded retrieval is citable and testable.
**Implications.**
- RagCore is the single retrieval/orchestration API the AI Gateway calls.
- Ingestion and indexing are platform-owned, tenant-partitioned, refreshed on cadence.
- Responses trace to retrieved sources for evaluation and trust.

### P08 — Stateless compute, externalised state
**Statement.** Compute is stateless and horizontally scalable; durable/shared state lives in managed
services — Postgres (records), Redis (cache/coordination), Key Vault (secrets), ServiceNow (system of
record), AI Search (retrieval).
**Rationale.** Stateless services scale, restart and roll out safely; state embedded in compute defeats
elasticity and safe deployment.
**Implications.**
- Container Apps instances are disposable; losing one loses no state.
- No secrets/connection-strings in images — resolved from Key Vault via managed identity.
- ServiceNow stays the authoritative record; the platform is not a second source of truth.

### P09 — Least privilege and secretless-where-possible
**Statement.** Each component runs with minimum rights, authenticates to Azure with managed identities,
and retrieves unavoidable secrets from Key Vault at runtime.
**Rationale.** Broad standing credentials are the most common breach vector; scoped identities and
central secret custody shrink attack surface and make rotation routine.
**Implications.**
- Service-to-service/data access uses managed identity + RBAC over shared keys.
- Key Vault is the sole secret source; rotation needs no redeploy.
- Integration credentials are scoped to exactly the operations each adapter performs.

### P10 — Observability is built in, not added on
**Statement.** Every request carries an end-to-end correlation identifier; every tier emits traces,
metrics and logs to the shared stack (App Insights, Log Analytics, Azure Monitor) by default.
**Rationale.** An agentic multi-hop system is undiagnosable without correlated telemetry; retrofitting
after an incident is too late.
**Implications.**
- Correlation ID created at APIM, propagated through AI Gateway, RagCore, services and integrations.
- AI signals (tokens, cache-hit ratio, guardrail actions, per-model latency) are first-class metrics.
- OOTB dashboards and alerts from Azure App Insights.

### P11 — Integrations are adapters, not leaks
**Statement.** External systems (ServiceNow, M365/AD) are reached only through dedicated adapters that
encapsulate the external contract behind a stable internal interface.
**Rationale.** Direct coupling spreads vendor quirks, auth and rate limits across the codebase; adapters
localise that blast radius.
**Implications.**
- The Integration service resides on the back lane with connectivity to customer Entra as egress.
- The Integration service's SNOW adapter owns all ServiceNow CRUD; nothing else calls ServiceNow
  directly.
- The .NET M365/AD adapter owns all Graph/directory interaction and Entra manipulations.
- The same integration service is used for all future integrations.
- Rate limits, retries and idempotency live inside the adapter, not in callers.

### P12 — Immutable, pipeline-delivered artifacts
**Statement.** All runtime artifacts are built once as versioned images in CI, stored in ACR, and
promoted by reference across environments — never edited in place.
**Rationale.** Immutable, traceable artifacts make deploys reproducible and rollback trivial, and keep
the developer estate out of the runtime trust boundary.
**Implications.**
- Devs commit to Azure DevOps; the pipeline builds and pushes to ACR; runtime pulls from ACR only.
- No direct write access to running environments — promotion is by image digest.
- The digest that passed test is the digest that runs in production.

### P13 — Thin client, deep server
**Statement.** Synthia is a presentation/interaction shell; all business logic, orchestration, data
access and policy live server-side.
**Rationale.** A thin client is cheap to update, hard to tamper with, and keeps sensitive logic/data off
endpoints inside customer networks.
**Implications.**
- No tenant data, secrets or policy decisions are cached or evaluated on the client.
- Client releases can lead/lag the server because the contract is the APIM product surface.
- Endpoint compromise does not expose backend capability beyond the user's own scope.

### P14 — Evolvable by contract (alpha strategy)
**Statement.** Zone boundaries are defined by explicit contracts so components can be replaced, split or
scaled independently as the design hardens toward GA.
**Rationale.** Early platforms change shape; contract-first boundaries let internals refactor without
cross-team breakage and let alpha converge to GA without a rewrite.
**Implications.**
- Each service publishes a versioned interface; consumers code to the version.
- The "Alpha-Strategy" grouping is expected to decompose — nothing assumes co-location.
- Decisions are recorded as ADRs so rationale survives team/design change.

### P15 — Data sovereignty honoured per tenant
**Statement.** Data classification, residency and retention are decided per tenant and enforced by where
stores, indexes and models are provisioned and how long data persists.
**Rationale.** Tenants carry different legal and contractual obligations; a one-size store violates at
least one of them.
**Implications.**
- Retrieval indexes and persistence can be pinned to a tenant's required region.
- Retention windows and right-to-erasure are configurable per tenant and per data class.
- Model endpoints are selected to satisfy residency (regional Azure OpenAI / Foundry).

> **Reviewer note (P15):** "If there is need of data sovereignty needed then only this principle will be
> worked upon and may need separate installation altogether."

### P16 — Cost is a design constraint (FinOps)
**Statement.** Token consumption, cache effectiveness and compute are measured and budgeted; cost is
treated as a first-class non-functional requirement.
**Rationale.** Agentic workloads have highly variable unit economics; without per-tenant visibility, one
tenant's usage silently subsidises or starves others.
**Implications.**
- The AI Gateway meters tokens per model and enforces budget/throttle policy.
- Semantic-cache ROI is tracked and fed back into caching strategy.
- Cost signals are attributable per tenant for chargeback/showback.

## 4. Logical Architecture

The system is organised into six zones, each with a distinct trust boundary and rate of change.

| Zone | Responsibility | Primary components |
|---|---|---|
| Customer Plane | Customer-owned identity/productivity estate; federated in, never managed. | Customer Entra ID, Customer M365, customer network |
| Client Tier | Thin desktop experience for the end user. | Synthia thin client (Electron) |
| Edge & Identity | Single ingress, dual-population authN/Z, policy enforcement. | Azure APIM, Customer/Synoptek Entra, technician persona |
| AI Plane | Model access, agent orchestration, retrieval, tool calling, safety. | AI Gateway, Azure OpenAI, Foundry (TekAssist-Incident/KB), Content Safety, MCP connector |
| Application / Command Center | Business logic, integrations, identity, live approvals, admin, RAG API. | Angular UI, .NET services, Python integrations, RagCore FastAPI |
| Shared Platform & Records | System of record, cache, persistence, retrieval store, secrets, telemetry. | ServiceNow, Redis, Postgres, AI Search, Key Vault, App Insights, Log Analytics, Azure Monitor |

### 4.1 Zone intent

**Customer Plane.** Customer Entra ID and M365 sit inside the customer network and are federated in. The
platform consumes identity for authN and reads directory/productivity context via the M365/AD adapter,
but never manages customer objects.

**Client Tier.** Synthia (Electron) renders the assisted-service experience and calls the platform only
through APIM; it holds no business logic, secrets or tenant data (P13).

**Edge & Identity.** Front Door + WAF is the public edge; APIM behind it is the API trust boundary and
policy point — token validation, audience/persona resolution, the gateway-derived identity contract,
rate/quota, and routing (P01, P02, P03). APIM holds no tenant status.

**AI Plane.** The AI Gateway brokers all model calls and enforces Content Safety bidirectionally. RagCore
(a LangGraph orchestrator) drives the problem-management flow and grounds on two Foundry-hosted knowledge
sources — TekAssist-KB (SOPs) and TekAssist-Incident (historic incident resolutions) — reaching tools via
the governed MCP connector (P01, P04, P06, P07).

**Application / Command Center.** Azure Container Apps + Web Apps host the Angular UI, RagCore (LangGraph
orchestrator), .NET Identity/Approvals/Admin, and the M365/AD and ServiceNow adapters — stateless,
independently scaled (P08, P11, P14).

**Shared Platform & Records.** ServiceNow is a single shared cloud instance capturing incidents for all
tenants (reached only via the Snow adapter, which stamps the tenant field on every record); Redis,
Postgres and AI Search hold cache/records/retrieval; Key Vault custodies secrets; App
Insights/Log Analytics/Azure Monitor form the telemetry backbone (P08, P09, P10, P15).

## 5. Component Inventory

| Component | Zone | Role |
|---|---|---|
| Synthia thin client (Electron) | Client | End-user shell; calls APIM only. |
| Azure APIM | Edge & Identity | Single ingress; authN/Z, tenancy, throttling, routing. |
| Customer Entra ID | Customer | Customer user IdP; federated (read-only trust). |
| Synoptek Entra | Edge & Identity | Staff (technician/admin) IdP. |
| Azure AI Gateway | AI Plane | Broker for model/agent/tool traffic; safety, caching, metering. |
| Azure OpenAI | AI Plane | Foundation model access. |
| Foundry — IDX-Incident | AI Plane | Incident-data knowledge (historic corrective approaches); backed by Azure AI Search (single index, mandatory `tid` filter — tenant-scoped). |
| Foundry — IDX-KB | AI Plane | SOP / procedural knowledge base; backed by Azure AI Search (single index, mandatory `tid` filter — tenant-scoped). |
| Azure AI Content Safety | AI Plane | Bidirectional guardrail enforcement. |
| MCP connector | AI Plane | Governed tool / external-context access for agents. |
| RagCore (Python / LangGraph) | Command Center | Problem-management orchestrator (LangGraph state graph + HITL); grounds on TekAssist-KB + TekAssist-Incident. |
| Command Center (Angular) | Command Center | Staff web application. |
| Tenant & Configuration (.NET) | Command Center | Tenant registry and mapping, tenant status and lifecycle, entitlements, credential references. Does **not** resolve request principals — identity is derived once, at APIM. |
| Approvals Service (.NET) | Command Center | Owns the authoritative approval and consent records; verdicts arrive over the Staff API, notifications over SignalR. |
| Admin (.NET) | Command Center | Administration and tenant configuration. |
| Integrations — M365/AD (.NET) | Command Center | Adapter for Microsoft Graph / directory. |
| Integrations — Snow (Python) | Command Center | Adapter for all ServiceNow CRUD. |
| ServiceNow (shared cloud) | Shared / Records | Single shared cloud instance; captures incidents for all tenants (logical separation). |
| Azure AI Search | Shared / Records | Single underlying store for both TekAssist-KB (SOP) and TekAssist-Incident indexes; hybrid vector+keyword; 24h scheduled refresh. |
| Azure Redis Cache | Shared / Records | Cache, semantic cache, ephemeral coordination. |
| Azure Postgres | Shared / Records | Platform persistence (config, audit, approvals state). |
| Azure Key Vault | Shared / Records | Secret custody; runtime resolution via managed identity. |
| App Insights / Log Analytics / Azure Monitor | Shared / Records | Telemetry, logging, alerting. |
| Azure DevOps repo / ACR | Delivery | Source, pipeline, image registry. |
| Scheduled ingestion job (Durable Functions) | Delivery / Data | 24h scheduled (re)indexing of KB + incident data into Azure AI Search; chunking + embedding. |

## 6. Security Architecture

The platform assumes zero implicit trust between zones. Identity is verified, tenancy is enforced, and
the network is closed by default; every relaxation is explicit.

### 6.1 Identity & token flow
The platform follows the identity contract defined in `identity-plane.md`.

At a platform level:

```text
Human / Workload
      ↓
Front Door + WAF
      ↓
APIM / Gateway
      ↓
Private application capability
```

The Gateway validates the applicable API audience and passes the trusted identity context to the service. Services enforce operation/resource authorization and tenant admission according to the Identity Plane. The Overall Architecture does not redefine `(tid, oid)`, role semantics, Workload authority, tenant lifecycle, or approval identity.

For asynchronous execution, services persist the authority context required by the Identity Plane before work is released to background execution.

### 6.2 Network segmentation & zero-trust

- Front Door + WAF is the **sole public ingress**; APIM sits behind it as the API trust boundary. The
  APIM origin is protected by a network control limiting traffic to the Front Door backend path and an
  application-level check of the platform's Front Door identifier — neither is sufficient alone.
- The Container Apps environment uses internal-only ingress; services are not reachable from the
  internet.
- Postgres, Redis, AI Search, Key Vault, Azure OpenAI and Foundry are reached over Private Endpoints on
  the platform VNet; public network access is disabled.
- Egress is constrained; the ServiceNow and Graph adapters use controlled outbound paths.
- The Synthia endpoint inside the customer network reaches only the APIM public/private endpoint over
  TLS.

> **Decision — Front Door + WAF is the public edge; APIM is the API trust boundary behind it.**
> Clients reach the platform over Front Door (TLS), which forwards to APIM. All internal data/model PaaS
> use Private Endpoints on a VNet with public access disabled, and Container Apps use internal-only
> ingress. Service-to-service application calls also traverse Front Door and APIM; there is no internal
> application bypass.

### 6.3 Secrets & data protection

- No secrets in images or config; managed identity + Key Vault at runtime (P09).
- Data encrypted in transit (TLS) and at rest with customer-managed keys (CMK) as the platform standard,
  held in Key Vault.
- PII minimised in prompts and logs; guardrail and telemetry pipelines scrub sensitive fields.
- Tenant secrets (e.g. ServiceNow credentials) are namespaced and scoped per tenant.

### 6.4 Agentic threat considerations

| Threat | Vector | Control |
|---|---|---|
| Prompt injection | Malicious content in retrieved docs / tool output | Treat retrieved/tool content as data; inbound Content Safety; instruction/data separation (P04) |
| Unsafe output | Model generates harmful/non-compliant text | Outbound Content Safety before response returns (P04) |
| Cross-tenant leakage | Cache/index/row served to wrong tenant | `tid` re-asserted per tier; namespaced stores; tenant-scoped cache (P03) |
| Over-autonomy | Agent performs consequential action unsupervised | Approval-gated write-backs via Approvals service (P05) |
| Tool abuse | MCP tool invoked beyond intended scope | Governed MCP allow-list; least-privilege tool credentials (P09, P11) |
| Data exfiltration via egress | Adapter/tool sends data to unexpected destination | Constrained egress; recipients not derived from untrusted content |

## 7. Multi-Tenancy Model

Tenant identity and authorization are governed by `identity-plane.md`. This architecture document owns the **platform isolation mechanisms** that implement that contract.

- Shared platform services must enforce tenant-aware data access.
- Retrieval and cache capabilities must support tenant-scoped isolation.
- Operational staff views may be cross-tenant where explicitly authorized by the Identity Plane.
- Tenant-specific residency, retention and erasure requirements are implemented through the platform data architecture.

The platform must not introduce an alternate tenant authority or accept tenant identity from untrusted application input.

## 8. Data Architecture

### 8.1 Stores & purpose

| Store | Data held | Classification | Residency / retention |
|---|---|---|---|
| ServiceNow (shared cloud) | Incidents for all tenants (source of record) | Customer-confidential | Single shared instance; per-tenant separation by tenant field + row-level ACLs |
| Azure AI Search — IDX-KB (SOP) | SOP/procedural knowledge (chunked + embeddings) | Customer-confidential | Tenant-partitioned; tenant region; 24h refresh |
| Azure AI Search — IDX-Incident | Historic incident resolutions (chunked + embeddings) | Customer-confidential; PII-minimised | Tenant-scoped via mandatory filter; tenant region; 24h refresh |
| Azure Postgres | Tenant mapping, chat sessions, work items, approvals and consent, governance and script config, graph checkpoints, audit log | Operational + audit | Tenant region in case of data sovereignty needed, else single region for alpha; audit retained per policy |
| Azure Redis | Cache, semantic cache, ephemeral coordination | Transient | Short TTL; no durable PII |
| Key Vault | Secrets, connection material | Secret | Rotated; access audited |
| Log Analytics / App Insights | Telemetry, correlated logs | Operational (PII-scrubbed) | Retention per tenant/compliance |

### 8.2 Retrieval store & ingestion
### 8.2 Retrieval store & ingestion

Azure AI Search is the platform retrieval capability. It hosts the knowledge and incident corpora used by RagCore. Detailed index schemas, chunking, embedding, filtering, reranking and evaluation are defined in `RagAgent-Architecture.md`.

The platform architecture provides the network, data-residency, lifecycle and operational controls required by those retrieval services. Retrieval-specific behavior must not be redefined here.

### 8.3 Classification, residency & lifecycle

- Data is classified per tenant (confidential / operational / transient / secret); handling follows the
  class.
- Residency: retrieval indexes, persistence and model endpoints can be pinned to a tenant's required
  region if needed, else Synthia-level default; encryption at rest uses customer-managed keys (CMK) as
  standard (P15).
- Retention & erasure: retention windows and right-to-erasure are configurable per tenant and per class;
  erasure removes the record, its embeddings and derived cache. Because retrieval is strictly
  tenant-scoped, there is no cross-tenant corpus from which contributions must additionally be withdrawn.
- PII is minimised in prompts and telemetry and scrubbed in guardrail/logging pipelines.

## 9. AI & Agentic Architecture

The platform includes an agentic resolution capability implemented by **RagCore**. Detailed agent graph behavior, retrieval strategy, governance configuration, approval suspension/resume, tool binding, signed execution and evaluation are defined in `RagAgent-Architecture.md`.

### 9.1 Architecture-level responsibilities

- RagCore provides the agent orchestration capability.
- Azure AI Search provides the retrieval capability.
- The AI Gateway provides model/tool egress controls such as routing, metering, caching and safety controls.
- Consequential actions use the governed execution path defined by the RAG architecture.
- Agent components operate within the platform trust boundaries defined here and the identity/authority rules defined in `identity-plane.md`.

The Overall Architecture intentionally does not define the LangGraph node graph, retrieval thresholds, chunking strategy, approval state machine, action schema, tool-binding schema or evaluation metrics.

## 10. Integration Architecture

All external coupling is via adapters that expose a stable internal contract and absorb the external
system's auth, quirks, rate limits and failure modes (P11).

| Adapter | External system | Owns | Resilience patterns |
|---|---|---|---|
| Integrations — Snow | ServiceNow (shared cloud) | Incident capture + CRUD into the shared instance; stamps the tenant field on every record | Idempotency keys, retry w/ backoff, rate-limit handling, DLQ |
| Integrations — M365/AD (.NET) | Microsoft Graph / Entra | All directory and productivity interaction — reads and governed writes | Token caching, throttling compliance, retry |
| MCP connector | Governed tools / external context | Tool invocation surface for agents | Allow-list, least-privilege creds, timeouts |
| Durable Functions | Knowledge sources | Ingestion / embedding / indexing | Checkpointing, idempotent re-run, poison handling |

Consequential write-backs are approval-gated (P05) and idempotent so retries cannot double-post.
Case-lifecycle writes — create, journal, state transition, close — are classified `AUTO` in the operation
catalogue and therefore proceed without human approval. No service calls ServiceNow or Graph directly —
only the adapters do.

> **Reviewer note (Snow adapter row):** "I've sent over a full list of Snow Fields we'll look to ingest
> for validation from business — the tenant id will be part of the validation. I will update and resolve
> thread once this is confirmed from Chris."
>
> **Reviewer note:** "Tenant field is assumed right now — confirm with business and Snow TAM."

## 11. Key Interaction Flows

### 11.1 Problem-management flow (Synthia-triggered)
### 11.1 Problem-management flow (Synthia-triggered)

At platform level, an end-user request enters through the public edge and Gateway, reaches the agent capability, and may result in a guided response or governed execution. The detailed graph and decision sequence are defined in `RagAgent-Architecture.md`.

### 11.2 Elevated-approval branch (HITL)
### 11.2 Elevated-approval branch (HITL)

At platform level, a governed action may create an approval request, notify the staff surface through the realtime capability, and resume only after the authorized approval operation is accepted. The detailed suspend/resume and execution semantics are defined in `RagAgent-Architecture.md`; identity and authorization semantics are defined in `identity-plane.md`.

### 11.3 Knowledge ingestion

1. A scheduled ingestion job runs on the configured cadence, with 24 hours as the default, and supports
   incremental sync and full rebuild.
2. Knowledge comes from: ServiceNow KB/SOP content; Synthia-resolved tickets stored in PostgreSQL;
   manually resolved tickets loaded incrementally from ServiceNow.
3. The two resolved-ticket sources are normalized, deduplicated and merged into one canonical
   historical-resolution dataset.
4. Records are sanitized/anonymized as required and stamped with tenant/TID, source system, source
   record ID, resolution source, timestamps, version and lineage.
5. SOP/KB content is chunked and embedded into the tenant-protected KB index. Historical resolutions are
   chunked and embedded into the agreed incident index model.
6. Watermarks/checkpoints and stable document IDs make the pipeline incremental, idempotent and
   re-runnable without duplicate indexing.
7. Azure AI Search remains a derived retrieval store. ServiceNow remains the enterprise ITSM source of
   truth, while PostgreSQL stores Synthia operational data.

### 11.4 Build & deploy

1. Developers commit through the approved Azure DevOps branch/PR process.
2. CI runs code tests, contract tests, security scans and relevant AI/RAG/prompt evaluations.
3. Each service is built once as an immutable versioned container image and pushed to ACR. The same
   tested image digest is promoted across environments.
4. Infrastructure is deployed through IaC. Secrets and environment configuration are injected through the
   approved managed-identity/Key Vault path.
5. Database, index and schema migrations are controlled. RagCore releases also version graph/state
   schema, policy and prompt contracts so old paused checkpoints cannot resume under incompatible
   behavior.
6. Container Apps pulls the approved image digest and performs a controlled rollout with
   health/readiness checks.
7. Post-deployment checks validate RagCore, RAG, MCP/tools, checkpoint/resume and telemetry.
8. Rollback means redeploying the previous approved image/configuration version; no in-place production
   edits are allowed.

## 12. Deployment & Network Topology

The platform runs in Azure across availability zones, on a platform VNet with private connectivity to
all data/model PaaS. The as-designed physical deployment (Primary / Active region) is shown in
Appendix A, with a strengths/trade-offs assessment; the layer summary below is the intended topology (to
be finalised in IaC).

| Layer | Placement | Access |
|---|---|---|
| Edge | Front Door + WAF, then APIM | Front Door is the only public ingress; APIM is the API trust boundary behind it |
| Compute | Container Apps environment + Web Apps | Internal-only ingress; VNet-integrated |
| AI | Azure OpenAI + Foundry services + Azure AI Services (Content Safety) | Private Endpoint; public access disabled |
| Data | AI Search, Postgres, Redis, Key Vault | Private Endpoint; public access disabled |
| Delivery | ACR | Private pull via managed identity |
| Client | Synthia in customer network | Outbound TLS to APIM endpoint only |

Environments are separated (dev / test / prod) with identical IaC-provisioned topology and promotion by
image digest. Zonal redundancy is applied to stateful PaaS; multi-region is a documented option for
tenants requiring it (§13, §14).

## 13. DevOps & Delivery

- Source in Azure DevOps; trunk-based with PR gates; every change is reviewed and tested.
- CI builds immutable, versioned images; SAST/dependency and container image scanning run in-pipeline
  (supply-chain integrity).
- Images are pushed to ACR and promoted across environments by digest — never rebuilt per environment
  (P12).
- Infrastructure is defined as code (Bicep/Terraform); environments are reproducible and drift-detected.
- Runtime pulls from ACR via managed identity; no developer has direct write access to running
  environments.
- Prompt, model-binding and guardrail changes are versioned and gated by evaluation (§9.4).

## 14. Resilience, DR & BCP

Stateless compute recovers by redeploying immutable images; the recovery focus is externalised state and
external dependencies.

| Asset / dependency | RPO | RTO | Strategy |
|---|---|---|---|
| Postgres (config/audit/approvals) | ≤ 15 min | ≤ 1 h | Zone-redundant + PITR; geo-restore option |
| AI Search (both indexes) | Re-derivable | ≤ 2 h | Re-run the 24h ingestion job to rebuild KB + incident indexes |
| Redis (cache) | 0 (transient) | minutes | Rebuild on miss; no durable state |
| Container Apps / services | 0 (stateless) | minutes | Redeploy ACR digest; autoscale |
| ServiceNow (external) | Vendor SLA | Vendor SLA | Adapter retry/queue; degrade gracefully |
| Model endpoints | N/A | minutes | Gateway failover to alt provider/region (P06) |

### 14.1 Degradation modes

- Model/provider outage → gateway fails over to an alternate binding; if none, assist degrades to
  retrieval-only or a graceful message.
- ServiceNow unavailable → write-backs queue (idempotent) and replay; reads serve last-known context
  where safe.
- Retrieval store unavailable → responses fall back to ungrounded with an explicit low-confidence
  signal, or are withheld per policy.

## 15. Observability & Operations

- Correlation ID created at APIM, propagated through AI Gateway, RagCore, services and adapters (P10).
- Three pillars to App Insights / Log Analytics: distributed traces, metrics, structured logs — all
  tenant-tagged.
- AI-specific signals are first-class: tokens/model/tenant, cache-hit ratio, guardrail actions,
  per-model latency, cost-per-resolution.
- Dashboards and alert rules exist per tenant before go-live; SLO burn-rate alerts drive on-call.
- Runbooks cover provider failover, tenant onboarding/offboarding, key rotation, and re-indexing.

## 16. Cost Governance (FinOps)

- Per-tenant token and compute metering with provider-normalised units (P16).
- Budgets and throttles enforced at the AI Gateway; alerts on budget burn.
- Semantic-cache ROI tracked (spend avoided vs. cache cost) and fed back into caching/routing.
- Cost attributable per tenant for chargeback/showback; model routing chooses the cheapest binding that
  meets the quality bar.

## 17. Compliance, Audit & Governance

- Every consequential action is logged with the full actor chain — `requested_by`, `approved_by`,
  `executed_by` — plus execution mechanism, tenant, policy decision and outcome (P05, P10).
- Guardrail decisions and model interactions are auditable with correlation IDs (P04).
- Data residency, retention and right-to-erasure enforced per tenant; encryption at rest uses
  customer-managed keys (CMK) (P15, §8.3).
- Tenant-scoped grounding on the TekAssist-Incident corpus, PII minimisation on ingest, and TID
  provenance. Cross-tenant grounding is not performed.
- Least-privilege access with managed identity + RBAC; access to secrets and audit logs is itself
  audited (P09).
- Architecture decisions recorded as ADRs; changes to principles go through formal amendment (§3).

## 18. Cross-Cutting Traceability Matrix

| Concern | Mechanism | Principles |
|---|---|---|
| Identity & authZ | Single IdP (Entra), audience separation, identity derived once at APIM, tenant status enforced service-side, reasserted downstream | P02, P03 |
| Tenant isolation | `tid` per request/cache/index/row/log; namespaced stores; tenant-scoped cache; tenant-field + row-level ACLs on the shared ServiceNow SoR | P03, P08, P15 |
| AI safety | Bidirectional Content Safety; untrusted retrieved/tool content; logged decisions | P04, P07 |
| Governance of actions | Approval-gated consequential write-backs (verdict over Staff API); full decision audit | P05, P10 |
| Cost & performance | Provider-normalised metering, semantic caching, per-model latency | P06, P10, P16 |
| Secrets & least privilege | Managed identity + RBAC; Key Vault sole secret source; scoped adapter creds | P09 |
| Observability | End-to-end correlation IDs; AI signals; pre-go-live alerting | P10 |
| Resilience & scale | Stateless disposable compute; externalised state; independent scale-out | P08, P14 |
| Delivery integrity | Immutable digests from ACR; scanned pipeline; no direct env access | P12 |
| Data sovereignty | Regional pinning; per-tenant retention/erasure | P15 |

## 19. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Cross-tenant data leakage | High | Low | Defence-in-depth `tid` enforcement; tenant-scoped cache/index (P03) |
| Prompt injection via retrieved content | High | Medium | Untrusted-data handling; inbound Content Safety (P04) |
| Model cost overrun | Medium | Medium | Per-tenant budgets/throttles; caching; routing (P16) |
| Provider outage / rate limits | Medium | Medium | Gateway failover; graceful degradation (P06, P14) |
| Cross-tenant exposure in shared ServiceNow | High | Low | Tenant-field row-level ACLs; adapter tenant stamping; ACL isolation tests (P03) |
| ServiceNow write duplication | Medium | Medium | Idempotency keys in the adapter (P11) |
| Alpha grouping ossifies into a monolith | Medium | Medium | Contract-first boundaries; ADRs; decomposition plan (P14) |
| Endpoint compromise (customer network) | Medium | Low | Thin client; no data/policy on endpoint; scoped tokens (P13) |

*End of main document.*

---

## Appendix A — Azure Deployment Architecture: Diagram & Trade-offs

This appendix presents the physical deployment of the Command Center on Azure and an assessment of its
strengths and trade-offs. The topology shown is the **Primary (Active) region** — every element is
region-scoped and tagged "Primary," which is the intended unit of replication for a future secondary
region (see the multi-region open item, §20.2 of the source doc).

### A.1 Deployment walkthrough

| Tier | Azure service(s) | Role |
|---|---|---|
| Edge / global entry | Azure Front Door / App Gateway, Firewalls, WAF | Global ingress, TLS offload, WAF/DDoS, routing |
| API & AI gateway | API Management (APIM), AI Gateway | AuthN/Z, throttling, quota; Azure Content Safety; AI policy / guardrails / token metering |
| AI services | Azure AI Foundry, Azure OpenAI | Agent orchestration + model inference |
| Retrieval & knowledge | Azure AI Search, Azure Storage Files | KB (SOP) + Incident indexes; raw KB/incident source data |
| Application tier | Azure Container Apps — Admin, Tenant & Configuration, Integration, RagCore, Approval (+ internal ingress) | Business services and the LangGraph orchestrator; internal-only ingress |
| Admin UI & real-time | Azure App Service (Staff portal / Synthia Console), Azure SignalR | Staff web app; real-time approval notifications and live updates |
| Data & secrets | Azure Database for PostgreSQL, Azure Cache for Redis, Azure Key Vault | Persistence; cache / semantic cache; secrets + CMK |
| Observability | Application Insights, Log Analytics | Telemetry, tracing, diagnostics, monitoring |
| Identity | Microsoft Entra ID (tenant), Customer Entra (federated) | Dual-plane OIDC / JWT validation |
| External system of record | ServiceNow (egress via APIM) | Shared incident system of record; single controlled egress |

*Figure A-1 — Command Center: Azure deployment (Primary region).*

### A.2 Strengths (pros)

| Area | Why it is a strength |
|---|---|
| Managed edge security | Front Door + App Gateway + Firewalls + WAF give global ingress, DDoS/WAF, TLS offload and one edge-policy surface. |
| Single control plane | APIM + AI Gateway centralise authN/Z, throttling, quota and AI guardrails/metering/provider-abstraction — models can be swapped without touching services. |
| Serverless-style app tier | Azure Container Apps gives per-service autoscale (including scale-to-zero) and internal-only ingress, with far lower ops than AKS at this size. |
| All-PaaS data plane | Postgres, Redis, Key Vault, AI Search and Storage are managed (HA options, backups, private endpoints, CMK) — minimal undifferentiated ops. |
| Secretless identity | Managed identity + Key Vault + dual Entra federation mean no standing secrets and clean customer/staff plane separation. |
| Native observability | Application Insights + Log Analytics provide correlated traces, metrics and logs out of the box. |
| Managed real-time | Azure SignalR offloads websocket scale for approval notification and live updates; the verdict itself is an authenticated API call. |
| Controlled egress | ServiceNow, M365 is reached only via APIM egress — a single, auditable outbound path. |
| Region-stamped blueprint | Every component is tagged "Primary," so the same IaC can stamp a second region cleanly when DR is approved. |

### A.3 Trade-offs & risks (cons) with mitigations

| Area | Risk / limitation | Mitigation |
|---|---|---|
| Large service surface | Many PaaS services to secure, monitor and pay for; more moving parts to operate. | Landing-zone IaC, Azure Policy guardrails, per-tenant FinOps budgets, consolidate where possible. |
| Shared backbone dependencies | Key Vault, Redis and Postgres are common dependencies for many services (the Cache/Secrets/SQL fan-out) — degradation has wide blast radius. | Circuit breakers, timeouts, caching, graceful degradation (§14); zone-redundant SKUs. |
| Two gateways in the AI path | APIM + AI Gateway add hops/latency and risk double-processing of policy. | Clarify responsibilities, co-locate, and measure added latency against the P95 SLO (§2.3). |
| Cold-start / scale-to-zero | Idle Container Apps can add start-up latency to already latency-sensitive LLM flows. | Set minimum replicas / a warm pool for RagCore and other hot paths. |
| Model capacity & regional binding | Azure OpenAI quota/PTU limits and single-region endpoints; provider-outage risk. | Provisioned throughput; gateway failover to an alternate region/provider (Claude via Foundry, D-07). |
| APIM as egress chokepoint | APIM concentrates ServiceNow egress — a throughput/availability bottleneck for the shared SoR. | Scale APIM; adapter retry/DLQ/idempotency (P11); monitor egress health. |
| Premium-tier cost at scale | Front Door, APIM, SignalR, AI Search, OpenAI and Container Apps premiums compound at multi-tenant scale. | Right-size tiers; per-tenant metering and chargeback (P16). |
| Operational skill breadth | Many distinct Azure services to run well. | IaC, runbooks, a platform team and platform SRE on-call (§15). |

### A.4 How Does Overall Assessment Look?

This is a well-architected single-region Azure deployment that maximises managed services and
centralises policy at the edge and the AI gateway — appropriate for alpha / early-GA at moderate tenant
scale, with low operational overhead and strong security defaults. The principal gap is resilience
posture: everything runs in one active region, which is exactly the one decision still open. Recommended
next steps: (1) decide active-passive vs. single-region + geo-restore and record it; (2) set Container
Apps minimum replicas on hot paths to remove cold-start latency; (3) confirm the Azure OpenAI capacity
model (quota vs. PTU) and gateway failover; and (4) ensure private endpoints on all data/model PaaS.

---

*Synoptek — Confidential. Source: `Synthia-OverallArchitecture.pdf`, Solution Architecture Rev 1.0.*
