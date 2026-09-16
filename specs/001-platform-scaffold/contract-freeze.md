# Contract Freeze Report — Shared Contracts (Phase 2)

**Date**: 2026-09-16
**Reviewed**: `dotnet/src/Synthia.SharedKernel`, `dotnet/src/Synthia.Contracts`,
`ragcore/src/ragcore/domain`, `ragcore/src/ragcore/application/ports.py`
**Against**: `Synthia-Platform-Specification.md`, constitution v3.1.0, `spec.md`, `data-model.md`,
`contracts/`, `docs/adr/0001–0005`
**Scope**: review, then remediation of the four findings approved for fix.
**Revised**: 2026-09-16 — F-1, F-2, F-6 and F-7 applied and verified.

---

## Verdict

**Reviewed 2026-09-16, remediated the same day.** Nine findings were raised. **Four are now closed**
— the two contradictions and two of the gaps. Five remain open, none blocking, each scheduled
against the stage that consumes it.

No finding required an architecture change. Every fix was a type or signature correction inside the
existing design.

| # | Contract | Finding | Severity | Status |
|---|---|---|---|---|
| F-1 | Approval | `record_verdict` accepted `ApprovalState`, admitting `PENDING`/`EXPIRED` as a human verdict | **CONTRADICTION — HIGH** | **CLOSED** |
| F-2 | Approval | Consent recorded as `granted: bool` where the data model defines a two-value verdict | **CONTRADICTION — LOW** | **CLOSED** |
| F-6 | Operation | `OperationStatus` absent from the domain | GAP — MEDIUM | **CLOSED** |
| F-7 | Operation | `ExecutionMethod` absent from the domain | GAP — LOW | **CLOSED** |
| F-3 | Error | `AuthorizationExpired` problem type vs FR-EXEC-001 "expiry MUST NOT be reported as an error" | UPSTREAM TENSION — MEDIUM | **OPEN — needs a decision, not code** |
| F-4 | Principal | Audience/role-set consistency not enforced (§11.5 table) | GAP — MEDIUM | Open — Stage 5/6 |
| F-5 | Audit | Actor chain typed `object`; §28.2/§28.4 express a precise structure | GAP — MEDIUM | Open — Stage 12 |
| F-8 | Principal | Correlation acceptance validated in .NET only | GAP — LOW | Open — Stage 6 |
| F-9 | Idempotency | Port omits `operation_id`, which the data model carries | GAP — LOW | Open — Stage 8 |

---

## Remediation applied — 2026-09-16

### F-1 (closed) — the verdict type can no longer express a synthesized verdict

`ApprovalVerdict` introduced in both stacks with exactly two decided values, `approved` and
`rejected`. `ApprovalRepositoryPort.record_verdict` now takes it. `ApprovalState` is unchanged and
remains what it always modelled: the work item's field, which legitimately carries `pending` and
`expired`.

**The prohibited call no longer has anything to pass.** `record_verdict(verdict=EXPIRED)` does not
type-check because `ApprovalVerdict.EXPIRED` does not exist.

There is deliberately no `RejectAndTakeOver` member. §17.6 lists it as a staff *action*, but it is a
rejection **plus** a session transition to `staff_controlled` — two facts, recorded separately. A
third verdict value would make the takeover invisible to anything reading the verdict alone.

### F-2 (closed) — consent verdict is a named type

`ConsentVerdict` (`granted` / `refused`) replaces `granted: bool`, mirroring `consent.verdict` in
the data model and the two consent trigger kinds. Principle VI's prohibition on boolean parameter
flags is satisfied, and a test asserts the three — database enum, trigger kinds, domain type — do
not drift apart.

### F-6 (closed) — `OperationStatus`

Six members matching `operation.status`: `proposed`, `gated`, `authorized`, `executed`, `failed`,
`refused`. `gated` and `refused` are the reason the type is needed rather than folded into the work
item — `gated` records that governance evaluated the operation at all, and `refused` is where a
`NOT_ALLOWED` outcome is written, which FR-AUDIT-003 requires be as durable as a permission.

### F-7 (closed) — `ExecutionMethod`

Three members matching `audit_event.execution_method`: `workload`, `desktop_script`, `none`. §28.3
requires the execution *mechanism* to be recorded distinctly from the *actor*, and `none` exists so
refused, expired or cancelled work still produces a complete audit record.

### The fixes are guarded

`ragcore/tests/unit/test_verdicts.py` (21 assertions) and
`dotnet/tests/Synthia.SharedKernel.Tests/VerdictTests.cs` (7) assert the properties directly, and
both were verified to fail on a planted regression:

| Planted regression | Result |
|---|---|
| Port signature reverted to `ApprovalState` | `test_the_port_takes_a_verdict_not_a_state` fails |
| `TIMEOUT` added to `ApprovalVerdict` | `test_has_exactly_two_members` and the parametrized synthesized-verdict test both fail |

A bonus assertion was added while the file was open:
`Execution_treatment_still_has_no_default_member` guards the Phase 2 property that
`ExecutionTreatment` has **no** `Unknown`/`Default`/`None` member — easy to erode, and the reason a
missing treatment is unrepresentable rather than merely prohibited.

**Validation after remediation**: all 23 gates pass. .NET 76 tests (was 65), Python 61 (was 40).

---

## Still open

### F-3 — needs a decision, not a code change

Unchanged from the original review, and **deliberately not resolved in code**. FR-EXEC-001 says
"expiry MUST NOT be reported as an error"; `contracts/customer-api.md` says instruction fetch
returns **410** once the window elapses. Both are frozen and pull in opposite directions.

The reconciling reading is that expiry is not a *failure of the user's request* — it surfaces as
approved-but-not-executed per FR-EXEC-007 — while an API call against expired work still returns a
status. That reading is probably right, but a type definition is the wrong place to settle it
quietly, and Principle X prohibits encoding an architectural decision silently in implementation.

**It wants one sentence in `spec.md` or a short ADR.** `ProblemTypes.AuthorizationExpired` is left
as-is until then.

### F-4, F-5, F-8, F-9 — scheduled

| # | Lands at | Note |
|---|---|---|
| F-4 | Stage 5/6 identity middleware (T057, T068–T081) | Fails closed today: a Staff-audience request carrying `end_user` is denied by empty intersection. §11.5 wants it refused at the boundary instead |
| F-5 | Stage 12 audit writing (T178) | The weakest contract in the set. §28.2/§28.4 are precise; `actor_chain: object` expresses none of it |
| F-8 | Stage 6 RagCore middleware | `CorrelationId.TryAccept` exists in .NET only; Python has the constant but no validator |
| F-9 | Stage 8 idempotency (T119) | `idempotency_record.operation_id` is non-null in the schema, absent from the port signature |

---

\* Audit is not one of the ten requested contracts but is load-bearing for the Approval and
Operation contracts, so it is reported here rather than omitted.

---

## 1. Principal contract

**Files**: `Identity/Identifiers.cs`, `Identity/AuthenticatedPrincipal.cs`,
`Identity/PrincipalFactory.cs`, `domain/principal.py`

**Consistent with the specification.**

| §11.5 requirement | Contract |
|---|---|
| Five closed headers, no alternatives invented | `IdentityHeaders` — exactly five; `IDENTITY_HEADERS` mirrors it |
| Human identity is `(tid, oid)`, no other value | `HumanIdentity(EntraTenantId, PrincipalId)`, distinct types |
| Refuse absent, empty, unordered, duplicated, non-canonical, whitespace-padded, wrong case | All six refused in `PrincipalFactory.TryParseRoles`; matching is ordinal, no trimming |
| Canonical order ascending lexicographic | Checked with `CompareOrdinal`, strictly ascending |
| `end_user`/`none` never combine | `SentinelCombinedWithRole` |
| Complete role set must survive to the service | `RoleSet` carries the whole set; nothing collapses it |
| Credential class refused where unsupported | `classMatchesAudience`, `Unknown` → refuse |

**§6.2 persona derivation is structural rather than remembered.** `AuthorizableRoles` returns
`{end_user}` on the customer audience regardless of what the principal holds, so "a person on a
customer surface is an end user, staff included" is a property of the set every call site reads —
not a rule each call site must recall. This is the strongest part of the contract.

### F-4 — audience/role-set consistency is not enforced (GAP, MEDIUM)

§11.5 constrains the role set per audience:

| Context | Permitted set |
|---|---|
| Customer API, delegated | `end_user` |
| Staff API, delegated | any non-empty subset of `{administrator, senior_technician, technician}` |
| Workload API, app-only | `none` |

`PrincipalFactory.TryCreate` validates the *credential class* against the audience but never the
*role set*. A Staff-audience request carrying `end_user` is accepted.

**It fails closed** — `AuthorizableRoles` returns `{end_user}`, every staff operation intersects to
empty, and the request is denied. So this is not exploitable. But §11.5 says such a context is
**invalid and refused at the boundary**, and the contract admits it. A refusal at the edge and a
denial three layers in are not the same audit record.

### F-8 — correlation acceptance is validated in .NET only (GAP, LOW)

`CorrelationId.TryAccept` enforces ≤128 characters and an alphanumeric/`-_.` charset — the
log-injection guard. Python has `CORRELATION_ID_MAX_LENGTH = 128` as a constant and **no validator**.
Both deployables sit behind the same edge and accept the same header; today only one enforces the
rule. RagCore's identity middleware is Stage 6 (T068–T081), so this is scheduled rather than
forgotten — recorded so it lands with the rule already written.

---

## 2. Tenant context contract

**Files**: `Identity/TenantContext.cs`, `domain/tenancy.py`, `TenantRegistryPort`

**Consistent with the specification, and the best-defended contract in the set.**

The rule "tenant context MUST NEVER be accepted from an untrusted client field" is enforced by
construction, not by review. `TenantContext` has no public constructor; it comes only from
`TenantAdmission`, whose three factory methods correspond exactly to the three legitimate
provenances the specification names:

| Provenance | §reference | Factory |
|---|---|---|
| End user's own `tid`, admitted against the registry | §11.7, §25 | `FromAdmittedIdentity` |
| The durable work item | §11.6 rule 3, §18.3 | `FromWorkItem` |
| The platform object a staff action targets | §11.8, §11.6 rule 2 | `FromPlatformObject` |

There is deliberately no `FromRequest`, `FromHeader` or `Parse`. **A caller holding a
client-supplied tenant identifier has nowhere to go.** `TenantSource` is recorded on every context,
so provenance is auditable rather than inferred.

§25's "Gateway holds no tenant state" is respected: `TenantRegistryPort` is consumed service-side
and returns `None` for an unknown organisation (fail-closed). §30.3's "every service checks this
authoritative state" is supported by `status_for`, and `IsAdmitted` is checked at execution rather
than only at admission, which is what FR-EXEC-003 requires.

**Observation, not a finding.** §11.6 rule 5 requires tenant binding to be *monotonic* — "later
components may consume that binding but never replace or widen it". Immutability prevents mutating
a context; nothing prevents constructing a second, different one further down a call chain.
Monotonicity is therefore a runtime discipline here, not a type guarantee. Enforcing it would need
the binding to travel in an ambient scope, which is a Stage 5/6 middleware decision, not a shared
contract one.

---

## 3. Authorization contract

**Files**: `Authorization/StaffRole.cs`, `Authorization/RoleIntersection.cs`, `domain/roles.py`

**Fully consistent.** The strongest correspondence in the review.

| Constitution Principle II / §6.4 | Contract |
|---|---|
| Four roles, disjoint capabilities | `end_user`, `technician`, `senior_technician`, `administrator` (+ `none` sentinel per §11.5) |
| `administrator` does NOT imply `technician` | Asserted in both stacks, both directions |
| `principal ∩ accepted ≠ ∅` | `RoleIntersection.Evaluate` / `roles.evaluate` — the only primitive |
| Empty intersection denies | `DenialReason.EmptyIntersection` |
| An operation accepting no roles denies everyone | `OperationAcceptsNoRoles`, a **distinct** branch, not a special case |
| Union and nothing further | Asserted: holding `{technician, administrator}` does not grant `senior_technician` |
| No sorting, ranking, comparing | **Does not compile** in C#; **raises `TypeError`** in Python |
| Roles held at decision time recorded | `AuthorizationDecision.RolesHeldAtDecision`, on refusals too |

§6.5's Alpha mapping (`Synthia_Agents → technician`, `Synthia_Admins → administrator`) is correctly
**absent** from these contracts. It is Entra group configuration resolved at the Gateway, and
encoding it in the shared kernel would place tenant/identity configuration inside a type that no
deployable should be able to vary.

The `senior_technician` treatment matches §6.5 exactly: defined, no Alpha assignment, no operation
accepts it, and every one of its intersections asserted empty.

---

## 4. Operation contract

**Files**: `Governance/ExecutionTreatment.cs` (`OperationIdentity`), `domain/identifiers.py`

**Consistent on identity; incomplete on lifecycle.**

`OperationIdentity(CatalogueId, Version)` correctly binds the catalogue version into the identity,
which is what makes §17.6's "the approval is bound to the exact operation presented" enforceable —
a catalogue edit between approval and execution cannot silently change what a human authorised. It
matches `governance_record`'s composite primary key `(catalogue_id, version)`.

### F-6 — `OperationStatus` was absent from the domain (CLOSED 2026-09-16)

`data-model.md` defines `operation.status` as `proposed`, `gated`, `authorized`, `executed`,
`failed`, `refused`. **No domain type expresses it.** `WorkItemState` and `ApprovalState` were
modelled; the operation's own lifecycle was not.

This matters beyond tidiness: `refused` is how a `NOT_ALLOWED` gate outcome is recorded, and
`gated` is the state that distinguishes "governance evaluated this" from "this was never
evaluated". Without the type, both become strings at the persistence boundary.

### F-7 — `ExecutionMethod` was absent from the domain (CLOSED 2026-09-16)

`data-model.md` and T096 define `audit_event.execution_method` as `workload`, `desktop_script`,
`none`. §28.3 makes `executed_by` deliberately polymorphic and requires the execution mechanism to
be recorded distinctly from the actor. No domain type exists for it.

---

## 5. Governance treatment contract

**Files**: `Governance/ExecutionTreatment.cs`, `domain/governance.py`, `OperationCataloguePort`

**Fully consistent.**

Four treatments, exactly as §4.3 and `spec.md` name them, with **no `Unknown` or `Default` member in
either stack**. That absence is load-bearing and deliberate: a missing treatment is not a state the
type can represent, so "we could not determine the treatment, carry on" cannot be expressed. The
catalogue port returns `None` for an unknown operation and the docstring states plainly that `None`
is a **refusal, not a default** — which is what FR-AGENT-004 and Principle III require.

`CapabilityKind` matches FR-EXT-012's read/action tagging; `Unknown` defaults to the safe reading.
`VerificationOutcome` matches ADR-0004's three outcomes exactly, with `ClientAttested` documented as
never presentable as confirmed resolution.

`CatalogueEntry` carries `is_reference_fixture` and `requires_elevation`, matching
`governance_record` and ADR-0004's Alpha rule that elevation is always `false`.

**The decision to keep treatment policy out of the ports is correct and worth preserving.** The
catalogue is a port because entries are stored; the treatment decision is domain logic. Making it
injectable is the mechanism by which a model-supplied treatment would eventually arrive.
`TestAuthorizationIsNotAPort` guards this.

---

## 6. Approval contract

**Files**: `ApprovalRepositoryPort`, `ConsentRepositoryPort`, `domain/work.py`

### F-1 — the verdict parameter admitted a system-synthesized verdict (CLOSED 2026-09-16)

```python
async def record_verdict(..., state: ApprovalState, expires_at: datetime) -> bool
```

`ApprovalState` is the **work item's** approval state — `none`, `pending`, `approved`, `rejected`,
`expired` (`data-model.md`, `work_item.approval_state`). The **approval's own verdict** is a
different, two-valued enum: `approved`, `rejected` (`data-model.md`, `approval.verdict`).

By typing the verdict parameter as `ApprovalState`, the contract permits
`record_verdict(state=ApprovalState.EXPIRED)` and `record_verdict(state=ApprovalState.PENDING)`.

This contradicts three frozen statements:

- **§17.7**: "No timeout, no auto-reject, **no system-synthesized verdict**."
- **FR-INTR-008**: "Approval MUST be a human decision. There MUST be no system-generated verdict and
  no approval by timeout."
- **§17.8**: "`approved_by` therefore always means a human approved."

Expiry is a work-item transition performed by the expiry sweeper (T121), **never a recorded human
verdict**. The contract as written makes the prohibited call type-check.

**Correction** (not applied): introduce `ApprovalVerdict` with exactly `APPROVED` and `REJECTED`,
and take that. `ApprovalState` stays as the work-item field it models. The same split is needed in
the .NET stack, which currently models neither.

### F-2 — consent verdict was a boolean (CLOSED 2026-09-16)

```python
async def record(..., granted: bool) -> bool
```

`data-model.md` defines `consent.verdict` as a two-value enum `granted`/`refused`, and
`contracts/triggers.md` carries `consent.granted`/`consent.refused` as distinct kinds. The
constitution prohibits this directly: **"No boolean parameter flag that hides behaviour"**
(Principle VI). A call site reading `record(..., True)` says nothing.

**Correction** (not applied): a `ConsentVerdict` enum mirroring the data model.

### Binding completeness — observation

Principle III requires an approval to bind eight things: approver, tenant, work item, requested
operation, target, operation version and context, expiration, audit record. `record_verdict` binds
five explicitly (tenant, approval, approver, roles held, expiry); work item, operation+version and
target are reached indirectly through `approval_id`.

The bindings do exist — `approval.work_item_id` is a unique non-null FK, and `operation` carries
`catalogue_id`/`catalogue_version`. So this is a thinner interface rather than a missing guarantee,
and it is recorded as an observation rather than a finding. It is worth revisiting at Stage 13,
when the approval use case is written, because a signature that names all eight is self-documenting
in a way that a signature reaching through an id is not.

**Correctly modelled**: first-valid-verdict-wins is expressed in the return type (`True` = this
verdict decided, `False` = one already existed), matching FR-INTR-010. The 15-minute window is
`expires_at` supplied by the caller from `decided_at`, matching §17.7's second clock. Consent's
"only the requester" rule is documented as the caller's precondition, consistent with the port
storing a decision rather than making one.

---

## 7. Realtime contract

**File**: `domain/envelopes.py`

**Fully consistent.** Field-for-field with `contracts/notifications.md`:

| Envelope field | Contract |
|---|---|
| `kind`, `occurredAt`, `correlationId`, `sessionId`, `workItemId` | `NotificationEnvelope`, same five, nothing more |

All seven event kinds present and correctly named: `interrupt.pending`, `approval.decided`,
`work.progressed`, `work.completed`, `work.failed`, `instruction.ready`, `session.taken_over`.

The §26.2 rule — the channel is a leaf, never a link — holds structurally: the envelope carries **no
tenant, no role, no approval state, no target, no command content**, and the type has no field that
could. `NotificationPort.notify_user` returns nothing, so no caller can treat a notification as an
answer. This matches FR-IDENT-005 and FR-SURF-018.

---

## 8. Async message contract

**File**: `domain/envelopes.py`

**Fully consistent.** `TriggerEnvelope` carries exactly `work_item_id`, `correlation_id`, `kind` —
"that is the entire payload", as `contracts/triggers.md` requires. The frozen dataclass makes the
prohibited additions (tenant, requester, roles, action, target, approval state, expiry, command
content, credentials) impossible without editing the type, which is visible in a diff.

All four kinds present, and the closed set matches. `resumes_to_execution` correctly separates the
two granting kinds from the two refusal kinds, supporting the rule that a refusal "closes the work
honestly rather than leaving it suspended".

The §11.6 rule 3 statement — "async work inherits authority from durable state, not from the
trigger" — is stated in the docstring and enforced by the envelope having nothing else to inherit
from.

---

## 9. Error contract

**Files**: `Errors/ProblemTypes.cs`, `domain/errors.py`

Shape is consistent: `ProblemContract` mirrors RFC 9457 and adds `correlationId`, matching
`contracts/README.md` exactly. `DomainError` subclasses carry no provider or transport detail,
so "internal exception detail MUST NEVER reach a client" is supported by construction.

### F-3 — expiry is in the error vocabulary (UPSTREAM TENSION, MEDIUM)

`ProblemTypes.AuthorizationExpired` is defined, with the comment "Not an error condition" — inside
the *problem types* list. That is self-contradictory on its face, and it sits on a genuine seam in
the frozen documents:

- **FR-EXEC-001**: "Expiry MUST NOT be reported as an error."
- **`contracts/customer-api.md`**: instruction fetch "Returns **410** once the validity window has
  elapsed" — an error status.

Both are frozen, and they pull in opposite directions. The reconciling reading is that expiry is
not a *failure of the user's request* (it surfaces as approved-but-not-executed per FR-EXEC-007),
while an API call against expired work still needs a status code. That reading is probably right.

**The contract should not be the place that decides it.** I am flagging it rather than resolving it,
because picking a side in a type definition is exactly the "silent architectural decision" Principle
X prohibits. It wants one sentence in `spec.md` or an ADR.

**Note**: `ProblemTypes` members beyond this are not drawn from the specification — they were
derived from requirements (`Throttled` from FR-OPS-006, `TemporarilyUnavailable` from FR-EXT-022,
`NotFound` from the 404-over-403 rule). That derivation is sound, but the set is new vocabulary and
should be reviewed as such rather than assumed pre-agreed.

---

## 10. Idempotency contract

**Files**: `Governance/ExecutionTreatment.cs` (`IdempotencyKey`), `IdempotencyStorePort`,
`WorkItemRepositoryPort.claim`

**Consistent.** The two boundaries §29.4 requires are both present and correctly separated:

| Boundary | Protects | Contract |
|---|---|---|
| 1 — atomic claim | the platform | `WorkItemRepositoryPort.claim`, conditional on `claimed_at IS NULL` |
| 2 — idempotency key | the external system | `IdempotencyStorePort.remember` / `replay` |

Both are documented as required with neither substituting for the other, matching `data-model.md`
and `contracts/workload-api.md`. `replay` returning the original outcome matches
`contracts/README.md`'s "a repeat returns the original outcome".

### F-9 — the port omits `operation_id` (GAP, LOW)

`data-model.md` gives `idempotency_record` a non-null `operation_id` FK; the port signature carries
only tenant, key and outcome. An implementation must obtain the operation from elsewhere to satisfy
the schema.

---

## Audit contract (not requested; reported because it is load-bearing)

### F-5 — the actor chain is untyped (GAP, MEDIUM)

```python
async def record(..., actor_chain: object, detail: object) -> None
```

§28.2 defines a precise structure (`requested_by → approved_by → executed_by`, each with stated
mutability), §28.3 makes `executed_by` polymorphic and distinguishes it from `downstream_actor` and
`execution_method`, and §28.4 lists **twelve** things a consequential record must answer.

`object` expresses none of it. The constitution requires explicit domain types "wherever a value
carries business meaning" (Principle VI), and the actor chain is the most meaning-bearing value in
the platform — it is what makes "100% audit coverage of consequential actions" checkable.

This is the one contract where the specification is most precise and the implementation is least so.

---

## What is consistent — summary

Six of the ten contracts are fully consistent with the frozen specification: **Principal**
(structure and header handling), **Tenant context**, **Authorization**, **Governance treatment**,
**Realtime**, **Async message**. **Idempotency** is consistent with one minor omission.

The three defended-by-construction properties are worth preserving through every later change:

1. `TenantContext` cannot be built from a client-supplied value — there is no such factory.
2. `AuthorizableRoles` returns `{end_user}` on customer surfaces, so the persona rule is not
   something a call site can forget.
3. Role ordering does not compile in C# and raises in Python.

---

## Disposition

Both contradictions are closed, and the two gaps that could be closed without pre-empting a later
stage are closed with them. The five remaining items are one upstream decision (F-3) and four gaps
scheduled against the stages that consume them.

**SHARED CONTRACTS FROZEN** for the ten contracts reviewed.

The freeze is on the contract *shapes*. Three carry a scheduled correction that does not change
shape — F-4 adds a validation, F-8 adds its Python counterpart, F-9 adds a parameter — and the
audit contract (F-5) is acknowledged as under-specified relative to §28 and will be typed when
Stage 12 writes the first audit record. **F-3 is an open question against the specification, not
against these contracts**, and is recorded so it is answered rather than absorbed.
