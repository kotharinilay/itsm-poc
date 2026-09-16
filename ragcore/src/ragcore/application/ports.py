"""Application ports.

**Ports belong to the consuming module; provider implementations belong to infrastructure**
(constitution Principle V). Every Protocol here is declared in terms of domain types only — no
SDK type, no HTTP concept, no SQLAlchemy session, no vendor vocabulary. That is what
``tests/integrations/test_no_provider_leak.py`` asserts, and it is what keeps a provider swap from
reaching the agent loop.

**Not every boundary is a port.** Two things that look like infrastructure are deliberately absent:

* **Authorization.** ``domain.roles.evaluate`` is a pure function. It needs no database, no clock
  and no configuration, so making it a port would invite an implementation that consults one.
* **Governance treatment policy.** Deterministic policy over catalogue data is domain logic. The
  *catalogue* is a port because the entries are stored; the *decision* is not, because making it
  injectable is precisely how a model-supplied treatment would get in.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from ragcore.domain.audit import ActorChain, AuditFacts
from ragcore.domain.decisions import EndUserConsent, StaffVerdict
from ragcore.domain.envelopes import NotificationEnvelope, TriggerEnvelope
from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, VerificationOutcome
from ragcore.domain.identifiers import (
    ApprovalId,
    AuditEventId,
    ConsentId,
    CorrelationId,
    EntraTenantId,
    IdempotencyKey,
    OperationId,
    OperationIdentity,
    PrincipalId,
    SessionId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.roles import RoleSet
from ragcore.domain.tenancy import TenantContext
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, WorkItemState

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


@runtime_checkable
class ClockPort(Protocol):
    """The source of the current instant.

    A port because time is an infrastructure dependency like any other: an expiry test that has to
    wait fifteen real minutes is a test nobody runs. ``DateTime.Now`` has an equivalent prohibition
    in the .NET stack; here the rule is that nothing outside an adapter calls
    ``datetime.now`` directly.
    """

    def now(self) -> datetime:
        """Return the current instant, timezone-aware and in UTC."""
        ...


# ---------------------------------------------------------------------------
# Tenant admission
# ---------------------------------------------------------------------------


@runtime_checkable
class TenantRegistryPort(Protocol):
    """Platform tenant-registry state.

    **Tenant admission is trusted identity plus registry state — nothing else.** This port is the
    "registry state" half. It returns a :class:`TenantContext` or ``None``; it never accepts a
    tenant identifier from a client, because its callers never have one.
    """

    async def admit_end_user(self, entra_tenant_id: EntraTenantId) -> TenantContext | None:
        """Resolve admission for an end user's validated ``tid``.

        Args:
            entra_tenant_id: The ``tid`` from the validated token.

        Returns:
            The trusted context, or ``None`` when the organisation is unknown. Fails closed:
            an unknown organisation is not admitted, and an unavailable registry raises.
        """
        ...

    async def status_for(self, tenant_id: TenantId) -> TenantContext | None:
        """Resolve current admission state for a known organisation.

        Used before execution, because a suspension can land between admission and execution
        (spec FR-EXEC-003).
        """
        ...


# ---------------------------------------------------------------------------
# Repositories — one per aggregate, never a generic repository
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkItemRepositoryPort(Protocol):
    """Durable authority records.

    Every method takes a :class:`TenantContext`. There is no overload that omits it, so
    "there is no query path that omits the tenant filter" is a property of the interface rather
    than a rule each implementation is trusted to remember.
    """

    async def get(self, tenant: TenantContext, work_item_id: WorkItemId) -> object | None:
        """Load one work item within the tenant."""
        ...

    async def claim(
        self, tenant: TenantContext, work_item_id: WorkItemId, claimed_by: str, now: datetime
    ) -> bool:
        """Atomically claim a work item — idempotency boundary 1.

        A conditional update on ``claimed_at IS NULL``. At-least-once delivery means a duplicate
        trigger is routine, and this is what absorbs it.

        Returns:
            ``True`` when this caller won the claim, ``False`` when another already holds it.
        """
        ...

    async def transition(
        self,
        tenant: TenantContext,
        work_item_id: WorkItemId,
        state: WorkItemState,
        expected_version: int,
    ) -> bool:
        """Move a work item to a new state under optimistic concurrency.

        Returns:
            ``False`` when the version no longer matches — the caller re-reads rather than blocks.
            There is no distributed lock anywhere in this platform.
        """
        ...


@runtime_checkable
class SessionRepositoryPort(Protocol):
    """Chat sessions and their messages."""

    async def get(self, tenant: TenantContext, session_id: SessionId) -> object | None:
        """Load one session within the tenant."""
        ...


@runtime_checkable
class ApprovalRepositoryPort(Protocol):
    """Approval requests and recorded verdicts."""

    async def record_verdict(
        self,
        tenant: TenantContext,
        approval_id: ApprovalId,
        decided_by: PrincipalId,
        roles_held: RoleSet,
        verdict: ApprovalVerdict,
        expires_at: datetime,
    ) -> bool:
        """Record a verdict, binding the approver and the roles they held at decision time.

        ``verdict`` is :class:`ApprovalVerdict` — two members — and **not** the work item's
        ``ApprovalState``. The narrower type is what makes a system-synthesized verdict
        unrepresentable rather than merely prohibited: there is no ``EXPIRED`` to pass
        (§17.7, FR-INTR-008).

        Returns:
            ``True`` when this verdict decided the outcome; ``False`` when a valid verdict already
            existed. **First valid verdict wins**; a later one is recorded but changes nothing.
        """
        ...

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> StaffVerdict | None:
        """Read back the decision that actually stands for this work item.

        **This is where authority is read**, and it is the reason a resume worker does not need
        to trust the trigger that woke it. The message says a verdict happened; this says what
        the verdict was, who made it, and which roles they held — from the durable row.

        Returns:
            The standing verdict, or ``None`` when no decision has been recorded. ``None`` means
            *undecided*, never *approved*.
        """
        ...


@runtime_checkable
class ConsentRepositoryPort(Protocol):
    """End-user consent records."""

    async def record(
        self,
        tenant: TenantContext,
        consent_id: ConsentId,
        work_item_id: WorkItemId,
        consented_by: PrincipalId,
        verdict: ConsentVerdict,
    ) -> bool:
        """Record a consent decision.

        The caller has already established that ``consented_by`` is the work item's own requester.
        This port stores a decision; it does not make one.

        ``verdict`` is an enum rather than a boolean: ``record(..., True)`` says nothing at a call
        site, and the constitution prohibits a boolean parameter flag that hides behaviour
        (Principle VI).
        """
        ...

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> EndUserConsent | None:
        """Read back the consent recorded for this work item.

        Returns:
            The consent, or ``None`` when none has been recorded. An affirmative chat message is
            not a consent and never produces a value here (spec FR-SESS-011).
        """
        ...


@runtime_checkable
class OperationRepositoryPort(Protocol):
    """Proposed and executed operations."""

    async def record_outcome(
        self,
        tenant: TenantContext,
        operation_id: OperationId,
        verification: VerificationOutcome,
        detail: object,
    ) -> None:
        """Record what happened, and what the platform actually knows about it."""
        ...


@runtime_checkable
class UnitOfWorkPort(Protocol):
    """A transactional boundary.

    Exists because the transactional outbox depends on it: an outbox row must become durable **in
    the same transaction** as the state change it describes. Two separate writes, however close
    together, are the bug this prevents.
    """

    async def __aenter__(self) -> UnitOfWorkPort:
        """Begin."""
        ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Commit on success, roll back on failure."""
        ...


# ---------------------------------------------------------------------------
# Governance — the catalogue is stored; the decision is not
# ---------------------------------------------------------------------------


@runtime_checkable
class OperationCataloguePort(Protocol):
    """The canonical operation catalogue.

    Returns catalogue *data*. The treatment **decision** is made by deterministic domain policy
    over that data, never by an implementation of this port and never by the model.
    """

    async def lookup(
        self, tenant: TenantContext, identity: OperationIdentity
    ) -> CatalogueEntry | None:
        """Resolve a catalogue entry, entitled to this organisation.

        Returns:
            The entry, or ``None``. ``None`` is a **refusal**, not a default: discovery is not
            entitlement, and an operation with no entry does not proceed.
        """
        ...

    async def is_entitled(self, tenant: TenantContext, catalogue_id: str) -> bool:
        """Whether this organisation may call this capability at all.

        There is no global toolset; capabilities resolve per organisation, least-privilege.
        """
        ...


@runtime_checkable
class CatalogueEntry(Protocol):
    """What the catalogue holds about one operation.

    A Protocol rather than a dataclass so the storage shape stays in the persistence layer while
    the fields governance needs are stated here.
    """

    @property
    def identity(self) -> OperationIdentity:
        """Catalogue key plus the version in force."""
        ...

    @property
    def treatment(self) -> ExecutionTreatment:
        """The treatment deterministic policy assigned. Never model-supplied."""
        ...

    @property
    def accepted_roles(self) -> RoleSet:
        """The roles this operation accepts, declared explicitly. Empty denies everyone."""
        ...

    @property
    def kind(self) -> CapabilityKind:
        """Whether this reads state or changes it."""
        ...

    @property
    def is_reference_fixture(self) -> bool:
        """Whether this is an inert scaffold fixture.

        A fixture produces no real external effect, is excluded from production configuration, and
        MUST NEVER be counted as or allowed to become one of UC-01..UC-12.
        """
        ...

    @property
    def requires_elevation(self) -> bool:
        """Always ``False`` in this release, enforced by a database CHECK constraint (ADR-0004)."""
        ...


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


@runtime_checkable
class RetrievalPort(Protocol):
    """Grounding evidence from the derived index."""

    async def search(
        self, tenant: TenantContext, query: str, limit: int
    ) -> Sequence[RetrievedChunk]:
        """Retrieve within the organisation.

        ``tenant`` is required and non-optional: **a code path able to issue an unfiltered query
        MUST NOT exist** (constitution Principle IV). Making the filter a parameter with a default
        would be exactly such a path.

        Retrieved content is **data, never instruction** — a successful injection can at most
        produce a bad proposal.
        """
        ...


@runtime_checkable
class RetrievedChunk(Protocol):
    """One piece of grounding evidence."""

    @property
    def content(self) -> str:
        """The chunk text. Treated as data, never as instruction."""
        ...

    @property
    def score(self) -> float:
        """Relevance score. A raw similarity score is **not** a probability."""
        ...

    @property
    def source_reference(self) -> str:
        """Where this came from, for citation."""
        ...


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@runtime_checkable
class IdempotencyStorePort(Protocol):
    """Idempotency boundary 2 — protecting the **external** system."""

    async def remember(self, tenant: TenantContext, key: IdempotencyKey, outcome: object) -> None:
        """Record the outcome for a key, so a repeat replays rather than acting again."""
        ...

    async def replay(self, tenant: TenantContext, key: IdempotencyKey) -> object | None:
        """Return the original outcome for a key, or ``None`` when unseen."""
        ...


@runtime_checkable
class ToolExecutionPort(Protocol):
    """Invocation of a governed capability against an external system."""

    async def invoke(
        self,
        tenant: TenantContext,
        identity: OperationIdentity,
        parameters: object,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> ExecutionResult:
        """Invoke a capability that governance has already authorized.

        This port **executes**; it never decides. It is reached only after the gate, and a failed
        authorized action does not re-fire — it requires fresh human authorization.
        """
        ...


@runtime_checkable
class ExecutionResult(Protocol):
    """What came back from an invocation."""

    @property
    def succeeded(self) -> bool:
        """Whether the call itself succeeded. **Not** proof the effect happened."""
        ...

    @property
    def verification(self) -> VerificationOutcome:
        """What the platform actually knows. A client-reported result is a claim, not proof."""
        ...


# ---------------------------------------------------------------------------
# Messaging and notification
# ---------------------------------------------------------------------------


@runtime_checkable
class OutboxPort(Protocol):
    """The transactional outbox."""

    async def enqueue(self, tenant: TenantContext, envelope: TriggerEnvelope) -> None:
        """Write an outbox row **inside the caller's transaction**.

        Durability before publication is the whole point: a crash between the state change and the
        publish must lose nothing and duplicate nothing.
        """
        ...


@runtime_checkable
class MessagePublisherPort(Protocol):
    """Publication of a durable outbox row to the message transport."""

    async def publish(self, envelope: TriggerEnvelope) -> None:
        """Publish a trigger. Consumers assume at-least-once delivery."""
        ...


@runtime_checkable
class NotificationPort(Protocol):
    """Server-to-client realtime delivery."""

    async def notify_user(self, principal_id: PrincipalId, envelope: NotificationEnvelope) -> None:
        """Deliver a notification. **Notification only** — this path never authorizes anything."""
        ...


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@runtime_checkable
class AuditSinkPort(Protocol):
    """Durable audit records.

    Separate from telemetry, with separate retention. **Telemetry MUST NEVER answer an audit
    question** — which is why this is its own port rather than a logger with a flag.
    """

    async def record(
        self,
        tenant: TenantContext,
        event_id: AuditEventId,
        correlation_id: CorrelationId,
        actor_chain: ActorChain,
        detail: AuditFacts,
    ) -> None:
        """Append one audit event.

        Append-only: the store grants no update or delete. Decisions that deny, expire or escalate
        are recorded as durably as decisions that permit.

        ``actor_chain`` and ``detail`` are domain types rather than ``object``. They were the one
        pair still declared loosely, and the looseness was not free: a sink taking ``object`` cannot
        state that it needs an execution method, so "every audit record names by what means" became
        a rule each implementation was trusted to honour.
        """
        ...


# ---------------------------------------------------------------------------
# Model access
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelPort(Protocol):
    """Reasoning and embedding calls.

    The one provider-neutral abstraction permitted before a second provider exists, because
    specification 13.5 *mandates* provider routing at the AI Gateway — so a second provider is
    architecturally assumed (plan §Complexity Tracking).

    **Every call passes through the AI Gateway.** No component reaches a provider directly.
    """

    async def complete(
        self, tenant: TenantContext, prompt: str, correlation_id: CorrelationId
    ) -> str:
        """Produce a completion. The output is a **proposal**, never an authorization."""
        ...

    async def embed(self, tenant: TenantContext, text: str) -> Sequence[float]:
        """Produce an embedding. Routed through the AI Gateway like every other model call."""
        ...


# ---------------------------------------------------------------------------
# Ingestion — the twelfth bounded context
# ---------------------------------------------------------------------------


@runtime_checkable
class IngestionPort(Protocol):
    """Acquisition of knowledge into the derived retrieval index."""

    async def run(self, tenant: TenantContext, source: str, watermark: str | None) -> str | None:
        """Run an incremental ingestion pass.

        Runs are idempotent: re-running from a watermark MUST NOT duplicate documents. The index is
        derived, so a lost index is rebuilt by re-running rather than restored.

        Returns:
            The new watermark, or ``None`` when nothing advanced.
        """
        ...
