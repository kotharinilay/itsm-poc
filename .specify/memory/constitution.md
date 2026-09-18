<!--
SYNC IMPACT REPORT
==================
Version change: 3.1.0 -> 3.2.0

Bump rationale: MINOR. The Principle V realization statement is updated to describe three
deployables rather than two, following Synthia-Platform-Specification.md §21.6 and ADR-0007, which
make Integrations a separately deployed service parallel to RagCore.

WHY MINOR AND NOT MAJOR. The versioning policy reserves MAJOR for removing or redefining a
principle, or relaxing a non-negotiable. None of that happens here:

  * No principle is removed or renumbered. Roman numerals I-X keep their numerals and meanings.
  * Principle V's RULE is unchanged — boundaries are mandatory, a context becomes a separately
    deployed service only by explicit ADR, and premature distributed decomposition is a defect.
    What changed is the REALIZATION PARAGRAPH describing which deployables currently exist. That
    paragraph has always been a statement of fact about the current architecture, and ADR-0007 is
    exactly the mechanism Principle V requires for changing it.
  * No non-negotiable is relaxed. Principle III is untouched: treatment assignment and role
    intersection stay with deterministic governance in RagCore, and the new service originates no
    authorization. Principle IV gains no second durable authority — governance_record stays with
    RagCore, `operation` remains the platform's conclusion, audit remains one store, and the
    Integrations Service owns only what nothing owned before.
  * The boundary rules are STRENGTHENED, not loosened: a new enforced deployment boundary, a
    narrowed credential blast radius, and authority re-verified at the point of effect.

Amended in this pass, four statements that had become false and one that had become incomplete:

  1. Principle V realization — "RagCore owns orchestration, execution and all state-changing
     operations; the .NET modular monolith is read-only" described two deployables and gave RagCore
     the execution leg. Replaced with the three-deployable table, the one-directional dependency,
     the no-shared-library rule, and the Integrations Service's grant limits.
  2. Principle V schema contract — "RagCore owns every migration" now reads as one gated Alembic
     project applying two schemas, with the column-scoped grant that stops an executing service
     rewriting its own instruction.
  3. Engineering Standards, Resilience — "RagCore calls MCP servers, the system of record, Graph
     and the realtime service" was factually wrong in three of its four clauses. RagCore calls
     none of the first three. Also records that the fifteen-minute window now spans two hops.
  4. Engineering Standards, Idempotency and messaging — records that each publishing deployable
     runs its own outbox, and that the two idempotency boundaries now sit in different deployables
     while both remain required.
  5. Compliance review — the forbidden-dependency list named only "between the two deployables".
     Now names the graph's actual prohibitions, including the reverse call from Integrations to
     RagCore and any RagCore path to an external system or connector credential.
  6. Principle III — "RagCore owns ... the verification workflow" would have put the verification
     CALL back in the orchestrator, which is external access Principle V removes from it. The
     workflow is now explicitly split: the call belongs to the Integrations Service, the CONCLUSION
     to RagCore. Tool selection is also named explicitly as RagCore's, so the Integrations Service's
     non-responsibility for it has a positive counterpart somewhere.
  7. Engineering Standards, Health — "/health/ready covers database and critical dependency
     readiness" was ambiguous about whether an external customer system counts, and a reasonable
     implementer could have included one. Readiness is now scoped to PLATFORM dependencies, with an
     explicit prohibition: an external system's outage is an operational condition, never an unready
     replica. Without this, one customer's ServiceNow outage could scale the platform to zero.

  8. Engineering Standards, Idempotency and messaging — the section said what at-least-once delivery
     obliges a consumer to do, and nothing about what happens to a message that CANNOT be processed.
     Dead-lettering was governed only by the platform specification. Now stated here as an
     engineering rule: dead-lettering is an operational handoff and never a retry; an
     out-of-contract field is refused rather than sanitised; and a dead-lettered message carrying
     authorized work is a GOVERNANCE failure that must surface to humans, because silently expired
     authority is authority nobody knows was spent.

Amendments 6, 7 and 8 were found by auditing the amended text against the Integrations Service
requirement set (spec FR-INTEG-001 through FR-INTEG-028) rather than by the reviewer pass that found
1 through 5. Amendments 6 and 7 clarify where a responsibility already sat under ADR-0007 and add no
rule. Amendment 8 does add a rule, which is squarely MINOR under the versioning policy ("materially
expanded guidance"); it relaxes nothing and contradicts nothing previously stated.

Migration path for work in flight: none required at the code level by THIS document. Work completed
under 3.1.0 remains valid; the integrations package relocates under ADR-0007 and plan Stage 16,
which is an architecture decision this constitution follows rather than creates. No task in
specs/001-platform-scaffold/tasks.md changes meaning as a result of this amendment, though the task
list is separately stale for other reasons recorded in plan.md §Phase Status.

Related records amended in the same change, per the rule that a divergence withdrawn in one record
and left standing in another is worse than either: ADR-0001 (amendment notice, divergence table),
ADR-0003 (second schema owner), ADR-0005 (adapters relocated), docs/adr/README.md (index).

-- 3.1.0 report retained below --

Version change: 3.0.0 -> 3.1.0

Bump rationale: MINOR. Two gaps found by the 2026-09-16 reviewer pass over
specs/001-platform-scaffold/checklists/ are closed by materially expanded guidance. No principle is
added, removed, redefined or relaxed, and no architectural rule changes.

  1. "Which change requires which category" added to Development Workflow and Quality Gates. The
     fifteen required categories already said what each PROVES; nothing said when each is OWED, so
     "a security fix needs a test" was not mechanically applicable at review.
     (architecture.md CHK065, implementation.md CHK085.)
  2. "Coverage" added to the same section, recording that no percentage threshold is set and that
     this is deliberate — the gate is behavioural. Neither position had been stated either way.
     (implementation.md CHK087.)

Migration path for work in flight: none required. Both additions describe obligations the fifteen
categories and the Principle VIII hard-failure gate already imposed; neither invalidates work done
under 3.0.0, and no task in specs/001-platform-scaffold/tasks.md changes meaning.

PRINCIPLE NUMBERING UNCHANGED. Roman numerals I-X keep their numerals and meanings.

-- 3.0.0 report retained below --

Version change: 2.9.0 -> 3.0.0

Bump rationale: MAJOR. One governance rule is redefined, not merely expanded. 2.9.0 ranked
authority as a single ladder: Identity Plane > this constitution > Synthia-Platform-
Specification.md > rule packs > convention — which placed the constitution ABOVE the platform
specification on architecture. 3.0.0 replaces that ladder with separated authorities: the
platform specification is authoritative on ARCHITECTURE, the constitution on ENGINEERING
GOVERNANCE, the plan on technical realization, the task list on executable work. No artefact
may be reinterpreted to silently override another. Everything else here is additive.

PRINCIPLE NUMBERING IS DELIBERATELY UNCHANGED. Roman numerals I-X are cited ~25 times across
docs/adr/0001-0005, plan.md, research.md, data-model.md and the checklists. Renumbering would
silently invalidate every citation, so each principle keeps its numeral and its core meaning
and is expanded in place.

Principles (all kept, all expanded):
  I.    Identity Is Derived Once, Authority Is Never Asserted   [+ zero trust, tenant admission]
  II.   Customer and Staff Authorization Are Separate and Non-Hierarchical [+ Entra group mapping]
  III.  Deterministic Governance Decides; the Model Only Proposes [+ approval binding, RagCore scope]
  IV.   Tenant Isolation Is Absolute; One Authority per Concern  [RENAMED from "PostgreSQL Is the
        Single Durable Truth"; same rule, widened to name each store's authority]
  V.    Modular Boundaries Are Mandatory                         [RENAMED from "RagCore Orchestrates,
        the Monolith Reads"; that rule is retained inside it, framed by the twelve contexts]
  VI.   Design for Change Without Speculation                    [RENAMED from "Explicit Boundaries,
        Simplest Sufficient Design"; + full SOLID, DRY-within-boundary]
  VII.  No Client Is a Security Boundary                         [+ Angular and Electron baselines]
  VIII. Provable by Audit and by Test                            [+ observability, hard failures]
  IX.   Scaffold Honestly; Do Not Invent Product                 [unchanged]
  X.    Decisions Are Recorded or They Do Not Exist              [+ MADR, C4, Diataxis]

Sections rebuilt: Engineering Standards and Technology Constraints; Development Workflow and
Quality Gates. Governance rewritten for the separated-authority model.

ADRs in force: docs/adr/0001-0005.

CONFLICT RECORDED, NOT SILENTLY RESOLVED:
  The input states "EF migrations are part of CI/deployment" and "use migration bundles".
  ADR-0001 and ADR-0003 make the .NET monolith READ-ONLY with no schema ownership:
  Database.Migrate(), EnsureCreated() and EF migration files are prohibited there, enforced by
  an architecture test, with Alembic owning every migration. Both positions are stated in
  Section 2 — the general rule as written, plus the fact that it has NO current application
  because the monolith owns no schema. If .NET is intended to own schema, ADR-0001 and
  ADR-0003 must be amended FIRST. This constitution does not decide that.

PLACEMENT NOTES — input said ".NET" where the architecture says otherwise:
  - Transactional outbox was listed under the .NET baseline. The monolith is read-only and
    publishes nothing, so the rule is stated platform-wide, where it binds RagCore.
  - Soft-delete, global query filters and audit columns are write-side schema concerns owned
    by RagCore's migrations; the monolith's published views must respect them.

Carried forward: assisted-response latency remains uncommitted pending a measured re-baseline.

Deferred intents: none. All input is governance content.
-->

# Synthia Constitution

## Core Principles

### I. Identity Is Derived Once, Authority Is Never Asserted

Assume zero trust. **Authentication is not authorization**: every consequential operation is
authorized on its own merits, every time.

Microsoft Entra ID is the only human identity provider. Human identity is `(tid, oid)`; no other value
is an identity key. The platform MUST NOT issue, store or broker user credentials.

Identity is derived exactly once, at the Gateway. Services MUST NOT parse an access token and MUST
consume only the closed Gateway-derived header contract.

**Tenant context MUST NEVER be accepted from an untrusted client field.** Tenant admission is trusted
identity plus platform tenant-registry state — nothing else. A client-supplied tenant, role or audience
MUST NEVER establish authority, and a governed staff action MUST NOT take its target tenant from a
client-controlled field. Triggers are untrusted and carry only opaque identifiers. The Workload
principal resolves its tenant only from the work item. Model output, retrieved content, fetched vendor
content, tool output, chat text and the realtime channel MUST NEVER confer identity, tenant or
authorization.

Front Door with WAF is the sole public edge; APIM is the API trust boundary. No application API is
reachable by a path that bypasses the gateway.

*Rationale:* A single derivation point is the only structure in which authority can be audited and
cannot be forged by a compromised surface, a misbehaving agent, or an untrusted message.

### II. Customer and Staff Authorization Are Separate and Non-Hierarchical

Customer and staff authorization are separate models. Neither inherits from the other, and a rule
written for one MUST NOT decide the other.

The roles are `end_user`, `technician`, `senior_technician` and `administrator`. They are **disjoint
capability sets, never a hierarchy**. `administrator` does NOT imply `technician`. A principal holding
several roles receives the union of those capabilities and nothing further.

Authorization is **set intersection**: `principal roles ∩ operation accepted roles ≠ ∅`. Every
operation declares its accepted set explicitly; an empty intersection denies; an operation that accepts
no roles denies everyone. Any implementation that sorts, ranks, compares or upgrades roles is a defect.

Initial-release assignment: `Synthia_Agents → technician`, `Synthia_Admins → administrator`.
`senior_technician` exists as a defined role that no operation accepts until one is explicitly
introduced.

**The surface decides which model applies, and a person MUST NOT be able to promote themselves.** Any
person acting on a customer surface is an end user — including staff — and their staff roles MUST NOT
be consulted there. The staff portal MUST NOT offer a way to originate a chat session. Take-over is
participation in an existing session, never origination, and MUST NOT transfer requester authority.

*Rationale:* Implied seniority is the classic route to silent privilege escalation. Set intersection is
decidable, testable, and cannot accidentally grant a capability nobody assigned.

### III. Deterministic Governance Decides; the Model Only Proposes (NON-NEGOTIABLE)

**The model proposes. Deterministic governance authorizes.**

RagCore owns orchestration, the state graph, retrieval coordination, planning, governance evaluation,
approval suspension and resume, model interaction, execution proposal, tool selection, and the
**conclusion** of the verification workflow. **RagCore is not the final authorization authority.**

**The verification workflow is split, and the split is the control.** The verification *call* is a
call to an external system and therefore belongs to the Integrations Service (Principle V), which
reports what it observed as `server_confirmed`, `client_attested` or `contradicted`. Whether the
platform may tell a user the issue is resolved is RagCore's conclusion and RagCore's alone. A service
that both acted and judged its own success would be reporting an attestation as a confirmation, which
is exactly what `client_attested` exists to prevent — and putting the verification call back in
RagCore would give the orchestrator the external access Principle V removes from it.

Execution treatment is exactly one of `AUTO`, `END_USER_APPROVAL`, `STAFF_APPROVAL`, `NOT_ALLOWED`,
assigned by deterministic policy from the canonical operation catalogue. The model MUST NEVER choose,
influence or override it. Side-effecting tools MUST NOT be reachable from an unconstrained agent loop.

**Discovery is not entitlement.** A capability advertised by an external or MCP server becomes callable
only once registered in the catalogue with a treatment and entitled to a specific tenant. There is no
global toolset; capabilities resolve per tenant, least-privilege. Adding a third-party system MUST
require only registration and entitlement, never a new authorization mechanism.

Human approval is authoritative for governed operations. Every approval MUST bind the authenticated
approver, the tenant, the work item, the requested operation, its target, the operation version and
context, an expiration, and an audit record. A pending approval may suspend indefinitely; once granted,
execution validity is fifteen minutes. Approval, consent, take-over and cancellation enter only through
authenticated APIs hosted by RagCore (ADR-0002).

**Approval never executes.** It records authority; execution happens separately through the Workload
path. Work-item authority fields are immutable at the database permission boundary. Execution MUST be
governed, idempotent, tenant-bound and inside the validity window. A failed authorized action MUST NOT
re-fire; it requires fresh human authorization, and approved-but-unexecuted work MUST surface to humans
rather than expiring silently.

SignalR delivers notification and results only — a leaf on every consequential path, never a link. A
client MUST NOT be the mechanism that resumes suspended work.

Scripts are predefined, versioned and platform-owned; the platform MUST NOT generate them at runtime.
The endpoint executes; it MUST NEVER decide.

*Rationale:* Agentic actions are consequential and often irreversible inside customer environments.
Keeping the decision deterministic and the human accountable is what makes autonomy safe to ship.

### IV. Tenant Isolation Is Absolute; One Authority per Concern

Tenant isolation MUST apply at **every** layer: gateway, APIs, database, retrieval, cache, memory,
tools, service integrations, realtime, telemetry and asynchronous messages. It MUST NOT rest on a
single chokepoint.

Cross-tenant retrieval is prohibited. Every retrieval request MUST carry the trusted tenant filter; a
code path able to issue an unfiltered query MUST NOT exist. There is no cross-tenant corpus. Aggregated
and derived figures MUST NOT reveal any single organisation's contribution.

**A second durable source of truth MUST NOT be introduced where the specification already names an
authority:**

| Concern | Authority | Everything else |
|---|---|---|
| Platform durable state | PostgreSQL | Authoritative |
| Cases | ServiceNow | System of record; **not** an approval authority |
| Retrieval | Azure AI Search | **Derived index**, never authoritative business state |
| Cache | Redis | **Transient only**, never a source of truth |
| Orchestration checkpoints | PostgreSQL, in the checkpointer's own schema | **No second durable checkpoint store may exist** |

Key Vault is the sole source of secret material. Zero cross-organisation exposure is a release gate.

*Rationale:* One deployment serves many customers, so isolation is a structural property rather than a
check. Naming a single authority per concern is what stops two stores drifting into disagreement with
no way to tell which is right.

### V. Modular Boundaries Are Mandatory

There is **one authoritative platform architecture**. These are the business responsibility boundaries,
and they are logical bounded contexts:

`Session` · `Work` · `Governance` · `Approval` · `Agent/RagCore` · `Retrieval` · `Tool Execution` ·
`Integration — ServiceNow` · `Integration — Microsoft Graph` · `Tenant & Configuration` · `Audit` ·
`Ingestion` (where applicable)

**Boundaries are mandatory even when responsibilities deploy together, and MUST NOT be collapsed for
implementation convenience.** Equally, a boundary MUST NOT become a separately deployed service without
an explicit architectural decision recorded as an ADR. Premature distributed decomposition is a defect,
not diligence.

**Dependency direction points inward, toward business and application policy.** Infrastructure is an
outer implementation detail. **Ports belong to the consuming module; provider implementations belong to
infrastructure.** Domain and application policy MUST NOT depend on an infrastructure implementation.
Cross-module abstraction MUST be justified by a real shared contract.

Within the current realization (ADR-0001, narrowed by ADR-0007), **three** application deployables:

| Deployable | Owns |
|---|---|
| **RagCore** | Orchestration, reasoning, governance, approval, the authority record, the atomic claim, and every state change to platform data. **It reaches no external system.** |
| **Integrations Service** | The tool catalogue, the connector registry, and all traffic to external systems — the sole holder of connector credentials |
| **.NET modular monolith** | Read-only. Query, listing, dashboard and reporting |

RagCore and the monolith have no application-level dependency in either direction — no API call, no
library reference, no deployment coupling — and meet only at PostgreSQL and asynchronous messaging.
**RagCore depends on the Integrations Service in one direction only**; results return asynchronously
rather than as a call, which is what keeps the graph acyclic. A reverse call from Integrations to
RagCore MUST NOT be introduced: it would make two services a distributed monolith. Module boundaries
inside the monolith are enforced by architecture tests, not convention.

**The two Python deployables share no library.** Correlation, error-contract, settings and telemetry
scaffolding are duplicated deliberately: a shared package would be a build-level dependency between
deployables required to have none, and it would not appear as a cross-tree path where the boundary
check could catch it. This is the "duplication across boundaries is cheaper than a false shared
contract" rule of Principle VI applied to a deployment boundary.

Because the deployables share one database, **the schema is the contract between them**. Alembic owns
every migration, as a single gated project applying both schemas: `platform`, written by RagCore, and
`integration`, written by the Integrations Service. Consumers read only through explicitly versioned
views, never altered in place: a new version is added alongside, the consumer migrates, the old is
dropped once unreferenced. **The Integrations Service holds no write grant on any `platform` base
table**, and may update only the result fields of an integration job, addressed by its identifier — it
MUST NOT be able to alter the instruction it was given, and that is enforced at the database
permission boundary rather than in application code.

*Rationale:* Boundaries that exist only in a diagram erode. Making them compile-time and test-enforced
is what keeps a modular monolith from becoming a ball of mud, and what keeps a later decomposition
possible.

### VI. Design for Change Without Speculation

SOLID is binding: single responsibility; open for extension, closed for modification; subtypes
substitutable for their base; no client forced to depend on methods it does not use; high-level policy
depending on abstractions rather than on detail.

Constructor injection only. Composition over inheritance. Tell, don't ask. Methods small and
intention-revealing. **No boolean parameter flag that hides behaviour.** No generic utility class that
becomes a dumping ground.

**Avoid speculative abstraction.** A provider-neutral abstraction MUST NOT be created until a real
second provider exists. DRY applies **within** a module boundary; unrelated modules MUST NOT be forced
into a shared abstraction merely to remove duplication — duplication across boundaries is cheaper than
a false shared contract.

Prefer explicit domain types over primitive strings wherever a value carries business meaning. Prefer
immutable models. Parse external input into precise internal types at the boundary. Side effects MUST
be modelled explicitly, and retries MUST be safe and idempotent.

**Business policy MUST NEVER be hidden inside framework infrastructure.** Configuration and secret
material live outside the code. Dependencies are explicit and injected; global state and service
locators are prohibited. A capability MUST NOT be built before a current requirement needs it.

*Rationale:* Most damage comes not from too little abstraction but from the wrong abstraction adopted
early and then defended. Speculative generality is the expensive kind of wrong.

### VII. No Client Is a Security Boundary

No client — Angular portal, Electron desktop, or any future surface — is a security boundary. Every
authorization, tenancy and policy decision is made server-side and re-verified server-side.

**Angular.** Role gating in the UI is convenience only; backend authorization is authoritative. Route
guards MUST NOT be treated as security boundaries. No secret may exist in browser code. CSP MUST be
supported, Angular sanitization rules followed, and `bypassSecurityTrust*` APIs avoided unless
specifically justified, reviewed and constrained. Presentation components MUST NOT implement
authorization policy.

**Electron.** `nodeIntegration=false`, `contextIsolation=true`, `sandbox=true` where compatible. A
narrow `contextBridge` surface only: raw `ipcRenderer` MUST NEVER be exposed, nor broad Electron or Node
APIs. **Every IPC sender and every IPC argument MUST be validated.** Navigation and new-window creation
are restricted; remote resources use HTTPS/WSS under a restrictive CSP; `webSecurity` MUST NOT be
disabled and insecure content MUST NOT be allowed. No remote code execution. `shell.openExternal` MUST
NEVER receive an untrusted URL. Electron stays on a currently supported release, and `file://` is
avoided where a safer protocol strategy applies. **No business authorization decision exists in the
renderer or in the main process.**

On the endpoint execution path: scripts are fetched per execution and MUST NOT be cached locally; the
instruction binds work item, catalogue entry, version and content hash, and a mismatch on any of the
four aborts before execution; script handling stays in the main process and never reaches the renderer.
Scripts run as the signed-in user and MUST NOT run elevated. **The endpoint executes only a versioned,
predefined, approved script, and never decides whether an operation is permitted.**

*Rationale:* Endpoints run inside customer networks and are outside the platform's control. Anything
they decide is a decision an attacker can make instead.

### VIII. Provable by Audit and by Test

Every request and every consequential operation MUST be traceable. A correlation identifier originates
at the public edge and propagates through every tier, appearing on every log record, trace,
notification, trigger and audit record. **W3C Trace Context** is used; a custom propagation header MUST
NOT replace it. Baggage carries only explicitly allowed values such as correlation id and tenant where
permitted.

Every consequential action MUST produce a durable audit record carrying the full actor chain: who
requested it, who approved it, which principal executed it, by what means, against which organisation,
and with what result. Audit is distinct from telemetry — separate stores, separate retention — and
telemetry MUST NEVER answer an audit question.

**Logs and telemetry MUST NOT leak** secrets, access tokens, authorization headers, sensitive customer
payloads, or any cross-tenant information.

**The platform MUST NOT claim to know more than it does.** A client-reported result is a claim, not
proof. Every execution records whether its outcome was server-confirmed, client-attested or
contradicted, and a client-attested outcome MUST NOT be presented as confirmed resolution.

Errors and invalid state surface at the earliest point they can be detected. Input is parsed into
precise types at the boundary. No caught error is silently swallowed. Any retriable operation MUST be
idempotent.

**These are hard failures, never warnings:** cross-tenant data leakage; consequential execution without
required authority; authorization bypass; execution caused by untrusted model output; duplicate
consequential execution from a retry; approval bypass; tenant context derived from an untrusted client
field.

*Rationale:* A platform acting agentically inside customer tenants is accountable for what it did. That
evidence must be a by-product of the design, not reconstructed later.

### IX. Scaffold Honestly; Do Not Invent Product

The current objective is a real, buildable reference scaffold — not the complete product.

The twelve initial ITSM use cases MUST NOT be invented. UC-01 through UC-12 are explicit placeholders
until their definitions are supplied, labelled as such and never dressed up as an implementation.

Any capability the scaffold does not support falls back to manual resolution or escalation. A fallback
MUST be explicit and visible; silently degrading, stubbing a success, or returning a plausible-looking
fabricated result is prohibited.

**Reference fixtures are permitted, and are never product.** Inert reference operations may exist so
that governance, consent and approval paths are demonstrable before any use case is defined. Each MUST
be labelled a scaffold fixture, produce no real external effect, be excluded from production
configuration, and MUST NEVER be counted as or allowed to become one of the twelve use cases.

*Rationale:* A scaffold that pretends to be a product is worse than no scaffold, because every later
decision is made against imagined requirements.

### X. Decisions Are Recorded or They Do Not Exist

Every architectural decision is recorded as an ADR in **MADR** structure under `docs/adr/`, with
sequential numbering and a status field. Each record distinguishes three things and never blurs them:
what the source requirements state, what was decided at implementation, and what remains unresolved.

**An architectural decision MUST NOT be encoded silently in implementation.** Public API contracts stay
explicit. Configuration assumptions are documented. **C4** diagrams are used where they clarify
structure, and prose documentation follows **Diátaxis**.

Architecture that conflicts with `Synthia-Platform-Specification.md` MUST NOT be introduced silently. A
divergence is either resolved in favour of the specification or recorded as an ADR naming the conflict,
the reason and the consequence.

*Rationale:* An unrecorded decision is re-litigated, and a silent divergence from the specification is
discovered only when it breaks something that trusted the specification.

## Engineering Standards and Technology Constraints

**Architecture baseline.** `Synthia-Platform-Specification.md` is the architecture source of truth. Its
standing constraints bind all downstream work except where this constitution records an explicit,
ADR-backed divergence. The Synoptek Identity Plane remains normative for identity.

**Language rule packs.** `principles.yaml`, `dotnet.yaml`, `dotnet_lang.yaml` (baseline `net10.0`),
`python.yaml`, `python_lang.yaml` (baseline `py312`) are normative. A `core` rule is non-negotiable; an
`extended` rule may be waived only with a recorded justification.

### Dependency injection

**.NET** — constructor injection only, via `Microsoft.Extensions.DependencyInjection`. The built-in
`IServiceProvider` is framework plumbing. Service Locator is prohibited; `IServiceProvider` MUST NOT be
injected into a business service for dynamic resolution; `BuildServiceProvider` MUST NEVER be called
during application configuration. Registration belongs in composition-root or module registration code.
Domain and application policy MUST NOT depend on an infrastructure implementation.

**Python** — explicit dependency injection, with FastAPI `Depends` at HTTP boundaries. Application
services stay independently testable. No hidden global mutable registry, and no concrete infrastructure
provider instantiated deep inside business logic.

**Angular** — Angular DI, `inject()` where appropriate, cohesive services, no global mutable state.

### .NET baseline

.NET 10 with ASP.NET Core, Minimal APIs, EF Core 10, Npgsql, built-in OpenAPI,
`Microsoft.Extensions.DependencyInjection`, `Microsoft.Extensions.Logging` and OpenTelemetry.
`Nullable=enable`, `TreatWarningsAsErrors=true`, analyzers at `latest-Recommended`,
`EnforceCodeStyleInBuild=true`, deterministic CI builds, central package management, and identical
strictness for test projects.

**APIs.** REST and resource-oriented. URI-segment versioning. Plural resource nouns; kebab-case for
multi-word segments; HTTP verbs carry the action; camelCase JSON in both directions. Action-style
routes only where an operation is genuinely command-like. Keyset/cursor pagination by default for large
or growing collections, with **opaque** cursors; offset paging only where explicitly justified. Query
filters are typed — arbitrary OData or expression-language filtering MUST NOT be exposed. Sorting is
`?sort=field` / `?sort=-field` over a **whitelisted** field set.

**Data access.** EF Core 10 on Npgsql. `AsNoTracking` for read-only queries. Parameterized queries
only. N+1 patterns are prevented; compiled queries where profiling or hot-path evidence justifies them.
**Optimistic concurrency only** — no pessimistic or distributed locking strategy. Read Committed by
default; Serializable only for explicitly identified invariant transactions. Soft-delete where required,
with global query filters for soft-deleted rows, and standard audit columns.

> **Schema ownership — a conflict recorded rather than resolved.** The general rule is that EF
> migrations run in CI and deployment, never at application startup, using migration bundles where the
> deployment topology requires them. **In this platform that rule has no current application:** ADR-0001
> and ADR-0003 make the .NET monolith read-only with no schema ownership, so `Database.Migrate()`,
> `EnsureCreated()` and EF migration files are prohibited there and an architecture test enforces it.
> Alembic owns every migration — a single gated project applying both the `platform` and `integration`
> schemas (ADR-0007) — and every consumer reads versioned views. Soft-delete, query filters and audit
> columns are therefore schema rules owned by those migrations, which the published views must
> respect. **If .NET is intended to own schema, ADR-0001 and ADR-0003 must be amended first.** This
> constitution does not decide that.

**Configuration.** `appsettings.json`, then `appsettings.{Environment}.json`, then environment
variables, then Container Apps secret-reference environment variables for secret material — later
overriding earlier. Application and domain code MUST NOT read `Configuration["Foo:Bar"]`. Use
`AddOptions<T>()` with `BindConfiguration(...)`, `ValidateDataAnnotations()` and `ValidateOnStart()`,
consuming `IOptions<T>`, `IOptionsSnapshot<T>` or `IOptionsMonitor<T>` as the lifetime requires. Secret
material resolves through managed identity and Key Vault.

**Validation and errors.** Built-in .NET 10 validation where appropriate. Validation errors are
distinguished from operational exceptions: Result types for expected application outcomes, exceptions
for exceptional failures. `IExceptionHandler` with RFC 9457 ProblemDetails at the API. Internal
exception detail MUST NEVER reach a client.

**Logging.** `Microsoft.Extensions.Logging`, structured, OpenTelemetry-integrated, with constant message
templates and PascalCase placeholders. `LoggerMessage` source generation on high-value or high-volume
paths. No `Console.WriteLine` outside explicitly allowed CLI or composition-root scenarios.

**Time.** `DateTimeOffset` throughout, from `DateTimeOffset.UtcNow` or an injected `TimeProvider`.
`DateTime.Now` is prohibited.

**Async.** Never block: no `.Result`, no `.Wait()`, no `GetAwaiter().GetResult()`. Async methods return
`Task`/`Task<T>`; `async void` only for genuine framework event handlers. `CancellationToken` propagates
through **every** async boundary, cancellation is honoured before and during blocking I/O,
`OperationCanceledException` is never swallowed, and shutdown permits clean Container Apps scale-in.

**Middleware order.** Exception handling → correlation/request id → request logging → trace context →
authentication → authorization → validation → endpoint. Correlation and trace context MUST be
established **before** request logging. Authentication MUST run before tenant resolution and
authorization.

**Correlation.** Accept `X-Correlation-Id` only when well formed; generate one when missing or invalid;
echo it in responses; bind it to the logging scope and the OpenTelemetry context.

**Health.** `/health/live` is process-only with no dependency checks. `/health/ready` covers database
and critical **platform** dependency readiness — the durable store, the message transport, the secret
store. `/health/startup` where useful.

**Readiness MUST NOT depend on an external customer system.** A ServiceNow, Graph or MCP-server
outage is an operational condition to be reported and degraded around, never an unready replica: a
readiness probe that failed on it would remove capacity at precisely the moment the fallback path
needs it, and would turn one customer's outage into a platform-wide one.

**Resilience.** `IHttpClientFactory` with typed clients and `DelegatingHandler` chains, using standard
`Http.Resilience`/Polly v8 capabilities applied consistently. `HttpClient` MUST NOT be instantiated
manually and one-off unmanaged clients MUST NOT be created. Resilience distinguishes transient from
non-transient failure. **Every outbound HTTP call carries an explicit timeout** — the Integrations
Service calls MCP servers, the system of record and Graph, and RagCore calls the Integrations Service,
the AI Gateway and the realtime service, all inside a fifteen-minute window, and a call without a
timeout can hold work past its expiry. **The window now spans two hops rather than one**, so the real
budget on an execution is tighter than the rule's arithmetic suggests.

**Idempotency and messaging** — platform-wide, not .NET-specific, since the monolith is read-only and
publishes nothing. Idempotency-key handling where required, with idempotency state persisted in
PostgreSQL. Outbound calls carry deterministic deduplication keys wherever the provider supports them.
Azure Service Bus Standard with a **transactional outbox in PostgreSQL**: an outbox record becomes
durable before asynchronous publication. **Each publishing deployable runs its own outbox** — RagCore
for triggers and integration commands, the Integrations Service for execution results. Consumers assume
at-least-once delivery, so every external side effect requires idempotency and a retry MUST NOT produce
a duplicate consequential action.

**The two idempotency boundaries now sit in different deployables, and both remain required.** The
atomic claim on the work item stays with the authority record in RagCore; the derived key carried to
the external system belongs to the Integrations Service. Neither substitutes for the other, and a test
that cannot say which boundary absorbed a duplicate is not evidence that either works — it passes
whenever one of them does.

**Dead-lettering is an operational handoff, never a retry.** A message that cannot be processed within
its validity window dead-letters rather than executing; a dead-lettered message MUST NOT be replayed
automatically, and recovery is fresh authorization rather than redelivery. **A message carrying a
field its contract does not permit is refused and dead-lettered, not sanitised** — stripping the field
and continuing returns success to whoever sent it and leaves the attempt indistinguishable from an
ordinary message. Where a dead-lettered message carried work a human had authorized, this is a
**governance failure and not merely an operational one**: it surfaces to humans as approved-but-not-
executed, with an alert, because silently expired authority is authority nobody knows was spent.

**Concurrency.** Distributed locking MUST NOT be an architectural primitive. Use optimistic concurrency
and atomic database claims; asynchronous jobs for singleton or background processing; state transitions
designed so retries are safe.

**Containers.** HTTP health probes, explicit resource limits, 25-second drain. .NET SDK container
publishing, multi-stage SDK → runtime, runtime image
`mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled` **pinned by digest** in production, running as
non-root UID 1654, shell-less and minimal, no package manager in the production image, read-only root
filesystem preferred. The image family, its policy and the digest-update process are documented.

### Python baseline

Python 3.12 or the repository `>=3.12` baseline, with `uv`, PEP 621 `pyproject.toml` and a committed
`uv.lock`. Ruff, strict mypy or Pyright, pytest, FastAPI, Pydantic, Pydantic Settings, LangGraph.

Ruff lint selection: `E, F, B, I, UP, S, PTH, SIM, ASYNC, DTZ`, plus `N` so naming is mechanically
enforced. **The Ruff formatter is authoritative.** CI runs strict type checking and pytest as failing
steps. Suppression is only a justified `# noqa: <code>` on the specific line; blanket ignores MUST NOT
be committed.

Prohibited: mutable default arguments; bare `except`; `print` in application or library code; `assert`
for runtime validation, which is permitted only in tests; `eval`/`exec` on untrusted data; **`subprocess`
with `shell=True` on any value derived from input — pass an argument list**, because the platform
executes catalogue scripts on customer endpoints and a shell string built from a parameter is a
command-injection path.

Required: type annotations on every public function and method; `pathlib` over `os.path`; `logging`;
f-strings; context managers for resources; modern typing (`list[T]`, `dict[K, V]`, `X | None`).
**Cancellation must propagate** — `asyncio.CancelledError` MUST NOT be swallowed, and async
infrastructure stays cancellation-safe. No global mutable state. HTTP and application orchestration are
separated from domain policy. Infrastructure dependencies are injected and external provider calls are
isolated behind ports and adapters. Pydantic models define boundary contracts; Pydantic Settings owns
configuration, and environment reads MUST NOT be scattered through business code.

### FastAPI architecture

FastAPI owns HTTP transport concerns only. **Endpoints contain no business policy.** Dependencies
establish the authenticated principal and request context; authorization decisions live in application
and domain policy. Request and response models are explicit Pydantic schemas. The API layer MUST NOT
reach persistence directly where a module boundary should exist. Async endpoints use async-compatible
dependencies, and cancellation and client-disconnect behaviour are respected. OpenAPI is generated from
the application contracts.

### LangGraph and RagCore

RagCore's responsibilities and its limits are in Principle III. LangGraph checkpoints are durable
orchestration state held in PostgreSQL per the authoritative architecture, in the checkpointer's own
schema, excluded from Alembic autogenerate. **No second durable checkpoint store may be introduced.**

### Angular

Standalone components, strict TypeScript, feature-oriented organization. Related component, template,
style and spec files are colocated where appropriate; kebab-case file naming; `.spec.ts` tests.
`inject()` where appropriate. Typed API contracts. Authentication and token handling, API client
infrastructure, and realtime/SignalR infrastructure are each centralized rather than repeated.
Accessibility is mandatory — WCAG 2.2 Level AA across all three surfaces, with no best-effort surface.
Current Angular testing defaults and the project-supported runner. A state-management framework MUST NOT
be adopted unless a requirement justifies it. Security obligations are in Principle VII.

### Model access

Every model call — reasoning and embeddings alike — passes through the **AI Gateway**, which owns
provider routing, provider-normalised token metering, per-organisation budgets and throttles, semantic
cache, and bidirectional content safety. No component reaches a provider directly. The AI Gateway is a
policy function, **not an identity boundary**: a call reaching a platform service still traverses APIM
and is authorized there and at the service. Per-organisation budgets and rate limits are enforced at the
AI Gateway and at APIM, not in application code.

### Non-functional commitments

99.9% monthly availability for platform APIs; zero cross-organisation exposure; zero standing secrets
with managed identity and RBAC throughout; RPO ≤ 15 minutes and RTO ≤ 1 hour for platform state;
retrieval indexes re-derivable within 2 hours; 100% audit coverage of consequential actions.

**No performance figure is committed, and none is an acceptance criterion.** The assisted-response
latency objective MUST be re-baselined against a measured hop count before any artefact treats it as
binding. Until then a release MUST NOT be gated on one, a merge MUST NOT be blocked by one, and an unmet
target is not a defect.

### Secrets

No credential in source code. No credential in tests. No credential in local configuration committed to
git. Key Vault and managed identity in every deployed environment.

## Development Workflow and Quality Gates

**Specification precedes implementation.** Work flows specification → plan → tasks → implementation.
Implementation artefacts derive from the architecture specification and MUST NOT introduce or redefine
an architectural rule of their own. If an implementation requirement conflicts with the specification or
this constitution, implementation stops and the architecture is resolved first, through an ADR.

### Required test categories

All are required; none substitutes for another.

| Category | Proves |
|---|---|
| Unit | Component behaviour in isolation |
| Integration | Real collaborators, real database, real messaging |
| Contract | Published API and message shapes, including between deployables |
| Authorization | Every operation against every role set, including the empty intersection |
| Tenant isolation | No path returns another organisation's data |
| Retrieval isolation | The tenant filter cannot be evaded, including by crafted input |
| Governance | Treatment comes from the catalogue and never from model output |
| Approval | Binding, expiry, first-valid-verdict-wins, no synthesized verdict |
| Idempotency | At-least-once delivery produces exactly one effect |
| Concurrency | Concurrent claims and decisions resolve to one outcome |
| Adapter | Provider behaviour stays behind its boundary |
| Architecture dependency | Module boundaries, banned APIs, the no-cross-deployable-dependency rule |
| Configuration validation | Options bind, validate and fail fast at start |
| Security | The prohibitions in this document are actually unreachable |
| End-to-end golden path | A representative journey completes through every layer |

A security or isolation fix without a failing-then-passing test is incomplete.

### Which change requires which category

The table above says what each category proves. This one says when it is owed, so the obligation is
mechanical at review rather than a matter of judgement. A change matching several rows owes all of
them. **Unit tests are owed by every change and are not repeated below.**

| A change that… | Owes |
|---|---|
| Adds or alters an API endpoint or message shape | Contract; authorization |
| Adds or alters an authorization rule, role set or accepted-role declaration | Authorization; security |
| Touches a query, repository, view or retrieval path | Tenant isolation; retrieval isolation where retrieval is involved |
| Adds or alters a catalogue entry, treatment policy or gate condition | Governance; authorization |
| Touches approval, consent, verdict or the resume path | Approval; concurrency; idempotency |
| Adds or alters an external side effect | Idempotency; adapter |
| Adds or alters a migration, table or published view | Integration; tenant isolation; architecture dependency |
| Adds or alters a module boundary, project reference or import | Architecture dependency |
| Adds or alters a configuration option or secret reference | Configuration validation |
| Touches an outbox, trigger, claim or worker | Idempotency; concurrency |
| Touches a client surface's primary journey | Frontend accessibility; end-to-end golden path where the journey is one |
| Fixes a security or isolation defect | The relevant category above, **failing first, then passing** |

### Coverage

**No line- or branch-coverage threshold is set, and none gates a merge.** This is deliberate, not an
omission. The gate is behavioural: the categories above are each required, and every protection named
as a hard failure in Principle VIII must have a test that fails when the protection is removed. A
percentage target would be satisfiable without any of that, and would reward exercising code over
proving a guarantee. Coverage MAY be measured and reported as information; it MUST NOT become a gate
without amending this section.

### Quality gate

No implementation phase is complete unless **all** of the following hold: the code builds; tests pass;
formatting passes; lint passes; static analysis passes; strict type checking passes; architecture rules
pass; tenant and security tests pass where relevant; and documentation is updated wherever an
architectural decision changed.

Every implementation phase MUST remain consistent with `Synthia-Platform-Specification.md`.

### Review

A change MUST NOT merge unless every gate above passes with no new suppressions, the change names the
module or deployable that owns the capability it touches, and any new complexity is justified. Reviewers
explicitly verify what no analyzer can prove: a single reason to change, correct ownership, that no
authority is taken from an untrusted source, that no role check ranks roles instead of intersecting
them, and that no business policy has been hidden inside framework infrastructure.

### Commits and versioning

**Conventional Commits.** Semantic versioning for versioned packages and components. Secrets MUST NOT be
committed. Generated build artifacts MUST NOT be committed.

## Governance

### Separated authorities

Each artefact is authoritative on its own axis. **No artefact may be reinterpreted to silently override
another.**

| Artefact | Authoritative on |
|---|---|
| `Synthia-Platform-Specification.md` | **Architecture** — structure, boundaries, trust model, data ownership |
| This constitution | **Engineering governance** — how software is built, tested, reviewed and secured |
| The implementation plan | **Technical realization** — how the architecture is built under these standards |
| The task list | **Executable work** — what is done, and in what order |

The Synoptek Identity Plane remains normative for identity, trust and authority, and this constitution
conforms to it. The language rule packs are normative within their language.

Where an architecture question arises, the platform specification answers it. Where an engineering
question arises, this constitution answers it. **Where the two genuinely conflict, implementation stops
and the conflict is recorded and resolved as an ADR** — never settled by whichever document the
implementer happened to read first.

### Amendment procedure

An amendment is a pull request changing this file that names the principle or rule affected, gives the
rationale, and describes the migration path for work already in flight. Amendments require review and
approval by the platform architecture owner. Silent divergence is a defect: practice that has drifted is
corrected in the practice or amended here, never left undocumented.

**Principle numbering is stable.** Roman numerals I–X are cited by ADRs and planning artefacts, so a
principle keeps its numeral for its life. A retired principle's numeral is never reused.

### Versioning policy

SemVer. MAJOR for a backward-incompatible governance change — removing or redefining a principle, or
relaxing a non-negotiable. MINOR for a new principle or materially expanded guidance. PATCH for
clarification and non-semantic refinement. Every amendment updates the version, the Last Amended date,
and the Sync Impact Report at the top of this file.

### Compliance review

Every pull request verifies compliance with these principles. Reviewers reject changes that add
complexity without justification, widen a module's responsibility, introduce an application dependency
the dependency graph does not permit — between RagCore and the monolith in either direction, or from
the Integrations Service back to RagCore — give RagCore a path to an external system or to a connector
credential, or take identity, tenant or authorization from an untrusted source.
Standing constraints are re-verified at each release gate alongside the zero-cross-tenant-exposure and
retrieval-evaluation gates.

Runtime development guidance for agents and contributors derives from this constitution and from
`Synthia-Platform-Specification.md`; where a guidance file disagrees with either, the authoritative
artefact for that axis wins.

**Version**: 3.2.0 | **Ratified**: 2026-09-15 | **Last Amended**: 2026-09-18
