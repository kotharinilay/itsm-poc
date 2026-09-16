"""In-memory doubles for every port, and a builder for a fully bound graph.

**These are fakes, not mocks.** Each one honours its port's contract — the catalogue really does
return ``None`` for an unregistered operation, the repositories really are tenant-scoped — so a
test that passes against them is testing behaviour rather than an interaction transcript. A mock
asserting "``lookup`` was called once" would still pass if the gate then ignored the answer.

Nothing here lives in ``src/``. The scaffold ships no adapters (Stage 6 non-goals), and these
exist so that absence does not stop the boundaries being tested.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from ragcore.application.ports import CatalogueEntry, ExecutionResult, RetrievedChunk
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
    OperationIdentity,
    PrincipalId,
    SessionId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, WorkItemState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies

FIXED_NOW = datetime(2026, 9, 16, 12, 0, 0, tzinfo=UTC)
"""A fixed instant. Every clock-dependent assertion is written against this, not against 'now'."""

EXECUTION_WINDOW = timedelta(minutes=15)
"""Once granted, execution validity is fifteen minutes (constitution Principle III)."""


class FakeClock:
    """A clock a test can move.

    The reason :class:`~ragcore.application.ports.ClockPort` exists: the execution window is
    fifteen minutes, and a test that proved expiry by waiting fifteen minutes would never run.
    """

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        """Return the current instant, timezone-aware and in UTC."""
        return self._now

    def advance(self, *, minutes: float) -> None:
        """Move the clock forward. There is no way to move it back."""
        self._now = datetime.fromtimestamp(self._now.timestamp() + minutes * 60, tz=UTC)


@dataclass(frozen=True, slots=True)
class FakeCatalogueEntry:
    """A catalogue entry, satisfying :class:`~ragcore.application.ports.CatalogueEntry`."""

    identity: OperationIdentity
    treatment: ExecutionTreatment
    accepted_roles: RoleSet
    kind: CapabilityKind = CapabilityKind.ACTION
    is_reference_fixture: bool = True
    requires_elevation: bool = False


class FakeCatalogue:
    """An operation catalogue holding whatever a test registered — and nothing else.

    **Discovery is not entitlement**, and the split is visible here: registering an entry and
    entitling an organisation to it are two separate calls, so a test that forgets the second gets
    the same refusal production would.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, int], FakeCatalogueEntry] = {}
        self._entitled: set[tuple[UUID, str]] = set()

    def register(
        self,
        catalogue_id: str,
        *,
        treatment: ExecutionTreatment,
        version: int = 1,
        accepted_roles: RoleSet | None = None,
        requires_elevation: bool = False,
    ) -> OperationIdentity:
        """Add an entry. Returns the identity the proposal must name to reach it."""
        identity = OperationIdentity(catalogue_id, version)
        self._entries[(catalogue_id, version)] = FakeCatalogueEntry(
            identity=identity,
            treatment=treatment,
            accepted_roles=accepted_roles or RoleSet.of(StaffRole.TECHNICIAN),
            requires_elevation=requires_elevation,
        )
        return identity

    def entitle(self, tenant: TenantContext, catalogue_id: str) -> None:
        """Entitle one organisation to one capability. There is no global toolset."""
        self._entitled.add((tenant.tenant_id.value, catalogue_id))

    def revoke(self, tenant: TenantContext, catalogue_id: str) -> None:
        """Withdraw an entitlement, as an offboarding or a policy change would."""
        self._entitled.discard((tenant.tenant_id.value, catalogue_id))

    async def lookup(
        self, tenant: TenantContext, identity: OperationIdentity
    ) -> CatalogueEntry | None:
        """Resolve an entry, or ``None`` — which is a refusal, not a default."""
        del tenant
        return self._entries.get((identity.catalogue_id, identity.version))

    async def is_entitled(self, tenant: TenantContext, catalogue_id: str) -> bool:
        """Whether this organisation may call this capability at all."""
        return (tenant.tenant_id.value, catalogue_id) in self._entitled


@dataclass(frozen=True, slots=True)
class FakeChunk:
    """One retrieved chunk."""

    content: str
    score: float
    source_reference: str


class FakeRetrieval:
    """Retrieval that records the tenant it was called with, per organisation.

    Storing chunks *per tenant* rather than in one list is deliberate: a fake with a single flat
    corpus would return another organisation's content happily, and an isolation test against it
    would prove nothing.
    """

    def __init__(self) -> None:
        self._corpus: dict[UUID, list[FakeChunk]] = {}
        self.calls: list[TenantContext] = []

    def seed(self, tenant: TenantContext, *chunks: FakeChunk) -> None:
        """Add chunks belonging to one organisation."""
        self._corpus.setdefault(tenant.tenant_id.value, []).extend(chunks)

    async def search(
        self, tenant: TenantContext, query: str, limit: int
    ) -> Sequence[RetrievedChunk]:
        """Retrieve within the organisation, and only within it."""
        del query
        self.calls.append(tenant)
        return self._corpus.get(tenant.tenant_id.value, [])[:limit]


class FakeModel:
    """A model that refuses to be called.

    Stage 6 makes no model calls. A fake that returned a plausible string would let a node start
    calling the model without any test noticing; this one turns that into a failure.
    """

    async def complete(self, tenant: TenantContext, prompt: str, correlation: CorrelationId) -> str:
        """Raise. Nothing in the scaffold may reach the model."""
        del tenant, prompt, correlation
        raise AssertionError("the scaffold makes no model calls (Stage 6 non-goals)")

    async def embed(self, tenant: TenantContext, text: str) -> Sequence[float]:
        """Raise, for the same reason."""
        del tenant, text
        raise AssertionError("the scaffold makes no model calls (Stage 6 non-goals)")


class FakeWorkItems:
    """Work items, with a claim that is genuinely single-winner."""

    def __init__(self) -> None:
        self._claimed: set[UUID] = set()

    async def get(self, tenant: TenantContext, work_item_id: WorkItemId) -> object | None:
        """Load one work item within the tenant."""
        del tenant
        return work_item_id

    async def claim(
        self, tenant: TenantContext, work_item_id: WorkItemId, claimed_by: str, now: datetime
    ) -> bool:
        """Claim atomically — the second caller loses, as in the conditional update."""
        del tenant, claimed_by, now
        if work_item_id.value in self._claimed:
            return False
        self._claimed.add(work_item_id.value)
        return True

    async def transition(
        self,
        tenant: TenantContext,
        work_item_id: WorkItemId,
        state: WorkItemState,
        expected_version: int,
    ) -> bool:
        """Accept the transition. Optimistic concurrency arrives with the real repository."""
        del tenant, work_item_id, state, expected_version
        return True

    async def list_expired(self, tenant: TenantContext, now: datetime, limit: int) -> list[Any]:
        """Work whose window has passed with no successful claim.

        Returns nothing: this fake seeds no work, so nothing it holds can have expired. Answering
        honestly matters more here than it looks — a fake inventing an expired item would let the
        sweeper's "expiry is not an error" path pass against work that never existed.

        It is implemented rather than omitted because
        :class:`~ragcore.application.ports.WorkItemRepositoryPort` declares it: a fake that
        satisfies a port partially is one the type checker cannot use to prove the graph is bound
        to the same contract production is.
        """
        del tenant, now, limit
        return []


class FakeApprovals:
    """Staff verdicts. First valid verdict wins, as the specification requires."""

    def __init__(self) -> None:
        self._by_work_item: dict[UUID, StaffVerdict] = {}

    def seed(self, work_item_id: WorkItemId, verdict: StaffVerdict) -> None:
        """Record a decision as though a human had posted it to the staff API."""
        self._by_work_item.setdefault(work_item_id.value, verdict)

    async def record_verdict(
        self,
        tenant: TenantContext,
        approval_id: ApprovalId,
        decided_by: PrincipalId,
        roles_held: RoleSet,
        verdict: ApprovalVerdict,
        expires_at: datetime,
    ) -> bool:
        """Record a verdict. ``False`` when a valid one already stood."""
        del tenant, approval_id, decided_by, roles_held, verdict, expires_at
        return True

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> StaffVerdict | None:
        """Read back the standing verdict, or ``None`` — which means undecided, not approved."""
        del tenant
        return self._by_work_item.get(work_item_id.value)


class FakeConsents:
    """End-user consents."""

    def __init__(self) -> None:
        self._by_work_item: dict[UUID, EndUserConsent] = {}

    def seed(self, work_item_id: WorkItemId, consent: EndUserConsent) -> None:
        """Record a consent as though the requester had posted it to the customer API."""
        self._by_work_item.setdefault(work_item_id.value, consent)

    async def record(
        self,
        tenant: TenantContext,
        consent_id: ConsentId,
        work_item_id: WorkItemId,
        consented_by: PrincipalId,
        verdict: ConsentVerdict,
    ) -> bool:
        """Record a consent decision."""
        del tenant, consent_id, work_item_id, consented_by, verdict
        return True

    async def decision_for(
        self, tenant: TenantContext, work_item_id: WorkItemId
    ) -> EndUserConsent | None:
        """Read back the recorded consent, or ``None``."""
        del tenant
        return self._by_work_item.get(work_item_id.value)


@dataclass(frozen=True, slots=True)
class FakeExecutionResult:
    """What a fake invocation returns."""

    succeeded: bool
    verification: VerificationOutcome


class FakeExecution:
    """A tool-execution port that records what it was asked to do.

    Records rather than performs. **No autonomous ITSM operation is implemented anywhere in the
    scaffold**, and the assertion that matters about this fake is usually ``invocations == []``.
    """

    def __init__(self, *, verification: VerificationOutcome = VerificationOutcome.CLIENT_ATTESTED):
        self.invocations: list[tuple[OperationIdentity, IdempotencyKey]] = []
        self._verification = verification

    async def invoke(
        self,
        tenant: TenantContext,
        identity: OperationIdentity,
        parameters: object,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> ExecutionResult:
        """Record the invocation and report an unverified success."""
        del tenant, parameters, correlation_id
        self.invocations.append((identity, idempotency_key))
        return FakeExecutionResult(succeeded=True, verification=self._verification)


@dataclass
class RecordedAuditEvent:
    """One captured audit event."""

    correlation_id: CorrelationId
    detail: AuditFacts


class FakeAudit:
    """An audit sink that keeps everything, so a test can assert a denial was recorded."""

    def __init__(self) -> None:
        self.events: list[RecordedAuditEvent] = []

    async def record(
        self,
        tenant: TenantContext,
        event_id: AuditEventId,
        correlation_id: CorrelationId,
        actor_chain: ActorChain,
        detail: AuditFacts,
    ) -> None:
        """Append one audit event."""
        del tenant, event_id, actor_chain
        self.events.append(RecordedAuditEvent(correlation_id, detail))


class FakeOutbox:
    """A transactional outbox that keeps enqueued envelopes."""

    def __init__(self) -> None:
        self.enqueued: list[TriggerEnvelope] = []

    async def enqueue(self, tenant: TenantContext, envelope: TriggerEnvelope) -> None:
        """Write an outbox row inside the caller's transaction."""
        del tenant
        self.enqueued.append(envelope)


class FakeNotifications:
    """A realtime channel that keeps what it was asked to deliver."""

    def __init__(self) -> None:
        self.delivered: list[tuple[PrincipalId, NotificationEnvelope]] = []

    async def notify_user(self, principal_id: PrincipalId, envelope: NotificationEnvelope) -> None:
        """Deliver a notification. Notification only — this path authorizes nothing."""
        self.delivered.append((principal_id, envelope))


@dataclass(slots=True)
class Harness:
    """Everything a graph test needs, constructed together and reachable individually.

    Attributes:
        deps: What the graph is built with.
        clock: The same clock the graph holds, so a test can move it.
        catalogue: The same catalogue, so a test can register and entitle.
        retrieval: The same retrieval port, for isolation assertions.
        approvals: The same approvals repository, for seeding a verdict.
        consents: The same consents repository, for seeding a consent.
        execution: The same execution port, for asserting nothing ran.
        audit: The same audit sink.
        tenant: An admitted organisation.
        requester: The end user the work belongs to.
    """

    deps: GraphDependencies
    clock: FakeClock
    catalogue: FakeCatalogue
    retrieval: FakeRetrieval
    approvals: FakeApprovals
    consents: FakeConsents
    execution: FakeExecution
    audit: FakeAudit
    tenant: TenantContext
    requester: PrincipalId

    def run_context(self, *, work_item_id: WorkItemId | None = None) -> RunContext:
        """Build a run context bound to this harness's tenant and requester."""
        return RunContext(
            tenant=self.tenant,
            requester=self.requester,
            correlation_id=CorrelationId(str(uuid4())),
            session_id=SessionId(uuid4()),
            work_item_id=work_item_id,
        )


def admitted_tenant(status: TenantStatus = TenantStatus.ACTIVE) -> TenantContext:
    """An organisation resolved from a validated end-user identity."""
    return TenantContext.from_admitted_identity(TenantId(uuid4()), EntraTenantId(uuid4()), status)


def build_harness(*, tenant: TenantContext | None = None) -> Harness:
    """Construct a graph's worth of fakes, wired the way the composition root will wire adapters."""
    clock = FakeClock()
    catalogue = FakeCatalogue()
    retrieval = FakeRetrieval()
    approvals = FakeApprovals()
    consents = FakeConsents()
    execution = FakeExecution()
    audit = FakeAudit()
    resolved_tenant = tenant if tenant is not None else admitted_tenant()

    deps = GraphDependencies(
        clock=clock,
        catalogue=catalogue,
        retrieval=retrieval,
        model=FakeModel(),
        work_items=FakeWorkItems(),
        approvals=approvals,
        consents=consents,
        execution=execution,
        audit=audit,
    )
    return Harness(
        deps=deps,
        clock=clock,
        catalogue=catalogue,
        retrieval=retrieval,
        approvals=approvals,
        consents=consents,
        execution=execution,
        audit=audit,
        tenant=resolved_tenant,
        requester=PrincipalId(uuid4()),
    )


def staff_verdict(
    identity: OperationIdentity,
    *,
    verdict: ApprovalVerdict = ApprovalVerdict.APPROVED,
    roles: RoleSet | None = None,
    decided_by: PrincipalId | None = None,
    decided_at: datetime = FIXED_NOW,
    expires_at: datetime | None = None,
) -> StaffVerdict:
    """A staff verdict as the approval repository would return it.

    ``expires_at`` defaults to ``decided_at`` plus the fifteen-minute window, matching what the
    verdict endpoint writes. Pass it explicitly — including ``None`` — to test the edges.
    """
    return StaffVerdict(
        approval_id=ApprovalId(uuid4()),
        decided_by=decided_by if decided_by is not None else PrincipalId(uuid4()),
        roles_held=roles if roles is not None else RoleSet.of(StaffRole.TECHNICIAN),
        verdict=verdict,
        bound_to=identity,
        decided_at=decided_at,
        expires_at=expires_at if expires_at is not None else decided_at + EXECUTION_WINDOW,
    )


def end_user_consent(
    identity: OperationIdentity,
    consented_by: PrincipalId,
    *,
    verdict: ConsentVerdict = ConsentVerdict.GRANTED,
    decided_at: datetime = FIXED_NOW,
    expires_at: datetime | None = None,
) -> EndUserConsent:
    """A consent as the consent repository would return it, carrying the same fifteen minutes."""
    return EndUserConsent(
        consent_id=ConsentId(uuid4()),
        consented_by=consented_by,
        verdict=verdict,
        bound_to=identity,
        decided_at=decided_at,
        expires_at=expires_at if expires_at is not None else decided_at + EXECUTION_WINDOW,
    )
