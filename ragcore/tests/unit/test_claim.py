"""The atomic claim and the derived idempotency key — **two boundaries, neither substituting**.

Boundary 1, the claim, stops a second execution *attempt*: a conditional update on
``claimed_at IS NULL``, so two consumers racing one work item produce one winner and one loser that
stops promptly. Boundary 2, the key, stops a second *effect* in the case the claim cannot cover — an
attempt that reached the far side, changed something there, and died before recording it
(spec FR-EXEC-004).

**These are unit tests of a rule the database enforces, and that needs saying.** The real predicate
is SQL: unclaimed, ``authorized``, and still inside its window. A fake that accepted every claim
would make ``claim_for_execution`` look correct while proving nothing, so the
:class:`ClaimablePredicate` below mirrors the SQL term for term — and
:meth:`TestTheFakeMirrorsTheRealPredicate.test_every_term_of_the_sql_predicate_is_mirrored` reads
``repositories.py`` and fails if the two ever part company. The integration proof against a real
PostgreSQL is ``tests/idempotency/test_duplicate_trigger.py``; this suite is the fast, exhaustive
half, and it is honest about being a stand-in.

Marked ``idempotency``: *proves at-least-once delivery produces exactly one effect*.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from ragcore.domain.identifiers import (
    EntraTenantId,
    OperationId,
    TenantId,
    WorkItemId,
)
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import WorkItemState
from ragcore.execution.claim import claim_for_execution
from ragcore.execution.idempotency import KEY_PREFIX, derive_key
from ragcore.persistence import repositories

pytestmark = pytest.mark.idempotency

NOW = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=15)
WORKLOAD = "workload-principal"


def _tenant() -> TenantContext:
    return TenantContext.from_admitted_identity(
        TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
    )


@dataclass
class Row:
    """A work item, in the four fields the claim predicate reads."""

    work_item_id: WorkItemId
    state: WorkItemState = WorkItemState.AUTHORIZED
    claimed_at: datetime | None = None
    expires_at: datetime | None = NOW + WINDOW


class ClaimablePredicate:
    """The claim, deciding exactly as ``WorkItemRepository.claim``'s ``WHERE`` clause decides.

    Four conditions, all of which must hold, mirroring the SQL:

    * the item belongs to this organisation — modelled by keying the store on the tenant, because
      the repository's ``_scope`` is not something a caller can omit;
    * ``claimed_at IS NULL``;
    * ``state = 'authorized'`` — which is what excludes a cancelled item;
    * ``expires_at > now`` — which is what excludes an expired one.

    Satisfies :class:`~ragcore.application.ports.WorkItemRepositoryPort`'s ``claim``.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], Row] = {}
        self.attempts = 0

    def seed(self, tenant: TenantContext, row: Row) -> Row:
        """Place a work item in one organisation."""
        self._rows[(str(tenant.tenant_id), str(row.work_item_id))] = row
        return row

    async def claim(
        self, tenant: TenantContext, work_item_id: WorkItemId, claimed_by: str, now: datetime
    ) -> bool:
        """One statement. The predicate and the write are not separable, as in PostgreSQL."""
        del claimed_by
        self.attempts += 1
        row = self._rows.get((str(tenant.tenant_id), str(work_item_id)))

        if row is None:
            return False
        if row.claimed_at is not None:
            return False
        if row.state is not WorkItemState.AUTHORIZED:
            return False
        if row.expires_at is None or row.expires_at <= now:
            return False

        row.claimed_at = now
        row.state = WorkItemState.CLAIMED
        return True

    # The rest of WorkItemRepositoryPort, implemented rather than omitted. A fake that satisfies a
    # port partially is one the type checker cannot use to prove the code under test is bound to
    # the same contract production is — the same reasoning as `tests/support/fakes.py`.

    async def get(self, tenant: TenantContext, work_item_id: WorkItemId) -> object | None:
        """Load one work item within the tenant."""
        return self._rows.get((str(tenant.tenant_id), str(work_item_id)))

    async def transition(
        self,
        tenant: TenantContext,
        work_item_id: WorkItemId,
        state: WorkItemState,
        expected_version: int,
    ) -> bool:
        """Accept the transition. Optimistic concurrency is not what this suite is about."""
        del expected_version
        row = self._rows.get((str(tenant.tenant_id), str(work_item_id)))
        if row is None:
            return False
        row.state = state
        return True

    async def list_expired(self, tenant: TenantContext, now: datetime, limit: int) -> list[Any]:
        """Unclaimed authorized items whose window has closed — the sweeper's one query."""
        expired = [
            row
            for (tenant_key, _), row in self._rows.items()
            if tenant_key == str(tenant.tenant_id)
            and row.claimed_at is None
            and row.state is WorkItemState.AUTHORIZED
            and row.expires_at is not None
            and row.expires_at <= now
        ]
        return expired[:limit]


class TestFirstClaimWins:
    """One winner, one loser, and the loser is not an error."""

    @pytest.mark.anyio
    async def test_the_first_caller_wins(self) -> None:
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4())))

        outcome = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW
        )

        assert outcome.won
        assert not outcome.should_stop
        assert outcome.claimed_by == WORKLOAD

    @pytest.mark.anyio
    async def test_the_second_caller_loses_and_stops(self) -> None:
        """A duplicate trigger is **routine traffic, not an incident**."""
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4())))

        first = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW
        )
        second = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by="another-replica", now=NOW
        )

        assert first.won
        assert not second.won
        assert second.should_stop

    @pytest.mark.anyio
    async def test_twenty_duplicate_deliveries_produce_exactly_one_winner(self) -> None:
        """At-least-once delivery, at the scale it actually arrives at."""
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4())))

        outcomes = [
            await claim_for_execution(
                store, tenant, row.work_item_id, claimed_by=f"replica-{index}", now=NOW
            )
            for index in range(20)
        ]

        assert sum(1 for outcome in outcomes if outcome.won) == 1
        assert store.attempts == 20

    @pytest.mark.anyio
    async def test_losing_reports_who_tried_rather_than_who_holds_it(self) -> None:
        """The loser knows its own claimant and nothing about the winner.

        Deliberate: reporting the holder would invite a caller to wait for it, and there is no lock
        anywhere in this platform. The loser stops.
        """
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4())))

        await claim_for_execution(store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW)
        loser = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by="replica-b", now=NOW
        )

        assert loser.claimed_by == "replica-b"


class TestTheClaimRefusesWhatIsNotClaimable:
    """Already claimed, expired, cancelled — three refusals, and none of them an error."""

    @pytest.mark.anyio
    async def test_an_already_claimed_item_is_refused(self) -> None:
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4()), claimed_at=NOW - timedelta(minutes=1)))

        outcome = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW
        )

        assert outcome.should_stop

    @pytest.mark.anyio
    async def test_an_expired_item_is_refused_and_that_is_not_an_error(self) -> None:
        """Expiry is a ``False``, never an exception (spec FR-EXEC-001).

        The distinction matters operationally: an expiry that raised would page somebody about a
        window closing, which is the system working.
        """
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4()), expires_at=NOW - timedelta(seconds=1)))

        outcome = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW
        )

        assert outcome.should_stop

    @pytest.mark.anyio
    async def test_an_item_expiring_exactly_now_is_refused(self) -> None:
        """The boundary, and it is exclusive: the SQL says ``expires_at > now``.

        An inclusive comparison would let work execute on the instant its authority ended, which is
        the kind of off-by-one that only ever shows up in a post-incident review.
        """
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4()), expires_at=NOW))

        assert (
            await claim_for_execution(store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW)
        ).should_stop

    @pytest.mark.anyio
    async def test_an_item_with_no_window_is_refused(self) -> None:
        """Fails closed. A missing window is not an unlimited one."""
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4()), expires_at=None))

        assert (
            await claim_for_execution(store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW)
        ).should_stop

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "state",
        [state for state in WorkItemState if state is not WorkItemState.AUTHORIZED],
    )
    async def test_only_an_authorized_item_is_claimable(self, state: WorkItemState) -> None:
        """Exhaustive over the state machine, so a new state is refused until somebody says so.

        ``CANCELLED`` is the case the specification names — cancellation is permitted before
        execution begins — and it is asserted here as one row of the table rather than on its own,
        because the rule is not "cancelled is special", it is "anything other than authorized is
        not claimable".
        """
        store = ClaimablePredicate()
        tenant = _tenant()
        row = store.seed(tenant, Row(WorkItemId(uuid4()), state=state))

        assert (
            await claim_for_execution(store, tenant, row.work_item_id, claimed_by=WORKLOAD, now=NOW)
        ).should_stop

    @pytest.mark.anyio
    async def test_another_organisations_item_is_not_claimable(self) -> None:
        """The tenant is not a filter the caller applies; it is one the interface requires."""
        store = ClaimablePredicate()
        owner, stranger = _tenant(), _tenant()
        row = store.seed(owner, Row(WorkItemId(uuid4())))

        assert (
            await claim_for_execution(
                store, stranger, row.work_item_id, claimed_by=WORKLOAD, now=NOW
            )
        ).should_stop


class TestTheFakeMirrorsTheRealPredicate:
    """The test above is only worth anything if the fake decides as the SQL decides."""

    def test_every_term_of_the_sql_predicate_is_mirrored(self) -> None:
        """Read the repository, and require each term of its ``WHERE`` clause to be present.

        Without this, tightening the SQL — or loosening it — would leave a green unit suite
        describing a rule the database no longer applies. A source-level assertion is coarse, and it
        is the only kind available to a test that deliberately does not connect to PostgreSQL.
        """
        claim = inspect.getsource(repositories.WorkItemRepository.claim)

        for term in (
            "claimed_at.is_(None)",
            "state == WorkItemState.AUTHORIZED.value",
            "expires_at.isnot(None)",
            "expires_at >",
            "self._scope(tenant, table)",
        ):
            assert term in claim, (
                f"WorkItemRepository.claim no longer contains {term!r}. The unit fake in this file "
                f"mirrors that predicate, and the two have parted company."
            )


class TestTheIdempotencyKeyIsDerivedNotRandom:
    """A random key is a new key on every attempt — the one thing an idempotency key must not be."""

    def test_the_same_inputs_always_produce_the_same_key(self) -> None:
        tenant = _tenant()
        work_item_id, operation_id = WorkItemId(uuid4()), OperationId(uuid4())

        keys = {derive_key(tenant, work_item_id, operation_id) for _ in range(25)}

        assert len(keys) == 1

    def test_a_different_operation_on_the_same_work_item_gets_a_different_key(self) -> None:
        """One work item can carry more than one operation; they must not deduplicate each other."""
        tenant, work_item_id = _tenant(), WorkItemId(uuid4())

        assert derive_key(tenant, work_item_id, OperationId(uuid4())) != derive_key(
            tenant, work_item_id, OperationId(uuid4())
        )

    def test_two_organisations_cannot_collide(self) -> None:
        """Hashed in, so identifiers reused across organisations still produce distinct keys."""
        work_item_id, operation_id = WorkItemId(uuid4()), OperationId(uuid4())

        assert derive_key(_tenant(), work_item_id, operation_id) != derive_key(
            _tenant(), work_item_id, operation_id
        )

    def test_the_key_discloses_no_organisation_and_no_identifier(self) -> None:
        """It travels to a vendor. A readable tenant in a third party's logs is a disclosure."""
        tenant = _tenant()
        work_item_id, operation_id = WorkItemId(uuid4()), OperationId(uuid4())

        key = derive_key(tenant, work_item_id, operation_id).value

        for secret in (str(tenant.tenant_id), str(work_item_id), str(operation_id)):
            assert secret not in key

    def test_the_key_is_versioned(self) -> None:
        """So the derivation can change without colliding with keys already in flight."""
        key = derive_key(_tenant(), WorkItemId(uuid4()), OperationId(uuid4())).value
        assert key.startswith(f"{KEY_PREFIX}:")

    def test_the_key_is_bounded_in_length(self) -> None:
        """A vendor header has a limit, and a truncated key deduplicates the wrong things."""
        key = derive_key(_tenant(), WorkItemId(uuid4()), OperationId(uuid4())).value
        assert len(key) <= 128


class TestTheTwoBoundariesAreNotTheSameBoundary:
    """Neither substitutes for the other, and the shapes say so."""

    @pytest.mark.anyio
    async def test_a_lost_claim_still_derives_the_same_key(self) -> None:
        """The key does not depend on who claimed, or on whether anybody did.

        This is the crash case in miniature: an attempt acted, died, and a later attempt — a
        different claimant, possibly a different replica — must present the key the far side already
        saw. A key derived from the claimant would present a new one and the effect would happen
        twice.
        """
        tenant = _tenant()
        work_item_id, operation_id = WorkItemId(uuid4()), OperationId(uuid4())
        store = ClaimablePredicate()
        row = store.seed(tenant, Row(work_item_id))

        first = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by="replica-a", now=NOW
        )
        # Released, as an escalation or a retry sweep would release it.
        store.seed(tenant, replace(row, claimed_at=None, state=WorkItemState.AUTHORIZED))
        second = await claim_for_execution(
            store, tenant, row.work_item_id, claimed_by="replica-b", now=NOW
        )

        assert first.won
        assert second.won
        assert first.claimed_by != second.claimed_by
        assert derive_key(tenant, work_item_id, operation_id) == derive_key(
            tenant, work_item_id, operation_id
        )
