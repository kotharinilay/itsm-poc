"""Each retention class is removable independently, and **expiring chat leaves audit intact**.

The property that matters most here is a negative one (spec FR-AUDIT-004, SC-AUDIT-002/003):
sweeping a conversation at ninety days must not remove the record of what was decided in it. A test
that only checked the conversation had gone would pass just as happily if the audit rows had gone
with it.

**The clock starts at the terminal state** (spec FR-SESS-020). A conversation open for six
months and resolved yesterday has ninety days left, not none — which is why
``content_expires_at`` is null while a session is live, and why the sweeper is driven by that
stamp rather than by ``created_at``.

**A missing override is the platform default, never unbounded retention** (spec FR-SESS-008).
Several of the tests below feed the resolver nothing, or something unusable, and assert it still
produces a window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from workers.retention_sweep import sweep_chat_content

from ragcore.domain.governance import ExecutionMethod
from ragcore.domain.identifiers import EntraTenantId, TenantId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalState, SenderKind, SessionState, WorkItemState
from ragcore.persistence import models
from ragcore.persistence.retention import (
    PLATFORM_DEFAULTS,
    RetentionClass,
    audit_retain_until,
    checkpoint_prune_after,
    content_expiry_for,
    window_for,
)


class TestTheWindowResolver:
    """Pure, and tested without a database because it needs none."""

    def test_every_class_has_a_platform_default(self) -> None:
        """A class with no default would be a class that silently never expired."""
        assert set(PLATFORM_DEFAULTS) == set(RetentionClass)

    def test_chat_content_defaults_to_ninety_days(self) -> None:
        """``data-model.md`` §Retention summary."""
        assert window_for(RetentionClass.CHAT_CONTENT, None).duration == timedelta(days=90)

    def test_audit_defaults_to_seven_years(self) -> None:
        """And is independent of chat retention in both directions."""
        assert window_for(RetentionClass.AUDIT, None).duration == timedelta(days=365 * 7)

    def test_work_follows_audit_rather_than_chat(self) -> None:
        """An audit event pointing at a work item that expired first answers nothing."""
        assert (
            window_for(RetentionClass.WORK, None).duration
            == window_for(RetentionClass.AUDIT, None).duration
        )

    def test_checkpoints_default_to_thirty_days_after_completion(self) -> None:
        """Pruned by a job we own — the checkpointer expires nothing itself (ADR-0003)."""
        assert window_for(RetentionClass.GRAPH_CHECKPOINT, None).duration == timedelta(days=30)

    def test_an_override_is_honoured_and_reported_as_one(self) -> None:
        """``is_override`` distinguishes a configured ninety days from a defaulted one."""
        window = window_for(RetentionClass.CHAT_CONTENT, {"chat_content": 30})
        assert window.duration == timedelta(days=30)
        assert window.is_override

    def test_a_missing_override_falls_back_to_the_default(self) -> None:
        """**Never unbounded retention.** The absence of configuration is not permission."""
        window = window_for(RetentionClass.CHAT_CONTENT, {"audit": 1})
        assert window.duration == timedelta(days=90)
        assert not window.is_override

    @pytest.mark.parametrize("bad", [0, -1, "ninety", None, 1.5, True])
    def test_an_unusable_override_falls_back_rather_than_disabling_retention(
        self, bad: Any
    ) -> None:
        """Retention broken by a typo would look exactly like retention never configured.

        ``True`` is in the list deliberately: it is an ``int`` in Python, and ``{"audit": true}``
        in a JSON override would otherwise resolve to a one-day audit retention.
        """
        window = window_for(RetentionClass.CHAT_CONTENT, {"chat_content": bad})
        assert window.duration == timedelta(days=90)
        assert not window.is_override


class TestTheClockStartsAtTheTerminalState:
    """Spec FR-SESS-020, and the reason ``content_expires_at`` is nullable."""

    @pytest.mark.parametrize(
        "state",
        [
            SessionState.CONVERSATIONAL,
            SessionState.RESOLVING,
            SessionState.AWAITING_USER,
            SessionState.AWAITING_CONSENT,
            SessionState.AWAITING_APPROVAL,
            SessionState.STAFF_CONTROLLED,
        ],
    )
    def test_a_live_session_gets_no_expiry(self, state: SessionState) -> None:
        """Including the three ``awaiting_*`` states, which persist indefinitely."""
        assert content_expiry_for(state, datetime.now(UTC), None) is None

    @pytest.mark.parametrize(
        "state",
        [SessionState.RESOLVED, SessionState.ESCALATED, SessionState.CLOSED_DECLINED],
    )
    def test_a_terminal_session_is_stamped_from_that_moment(self, state: SessionState) -> None:
        """Ninety days from *now*, not from when the conversation opened."""
        at = datetime.now(UTC)
        assert content_expiry_for(state, at, None) == at + timedelta(days=90)

    def test_an_organisation_override_shortens_the_stamp(self) -> None:
        """Configuration governs the window; it does not govern whether there is one."""
        at = datetime.now(UTC)
        assert content_expiry_for(SessionState.RESOLVED, at, {"chat_content": 7}) == at + timedelta(
            days=7
        )

    def test_audit_and_checkpoint_horizons_use_their_own_classes(self) -> None:
        """Three classes, three clocks. Sharing one would couple retentions that must not be."""
        at = datetime.now(UTC)
        assert audit_retain_until(at, None) == at + timedelta(days=365 * 7)
        assert checkpoint_prune_after(at, None) == at + timedelta(days=30)


@pytest.fixture
async def organisation(sessions: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """One organisation with a resolved conversation and the audit trail it left behind."""
    tenant_id, entra_tid = uuid4(), uuid4()
    session_id, work_item_id, requester = uuid4(), uuid4(), uuid4()
    message_id = uuid4()

    async with sessions() as session, session.begin():
        await session.execute(
            insert(models.TENANT_MAPPING).values(
                tenant_id=tenant_id,
                entra_tid=entra_tid,
                display_name="Contoso",
                status=TenantStatus.ACTIVE.value,
            )
        )
        await session.execute(
            insert(models.CHAT_SESSION).values(
                session_id=session_id,
                tenant_id=tenant_id,
                requester_oid=requester,
                state=SessionState.RESOLVED.value,
                content_expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await session.execute(
            insert(models.MESSAGE).values(
                message_id=message_id,
                session_id=session_id,
                tenant_id=tenant_id,
                sender_kind=SenderKind.AGENT.value,
                sender_oid=None,
                body="Resolved.",
            )
        )
        await session.execute(
            insert(models.SESSION_STEP).values(
                step_id=uuid4(),
                session_id=session_id,
                tenant_id=tenant_id,
                kind="retrieval",
                summary="Looked it up.",
            )
        )
        await session.execute(
            insert(models.FEEDBACK).values(
                feedback_id=uuid4(),
                message_id=message_id,
                session_id=session_id,
                tenant_id=tenant_id,
                given_by_oid=requester,
                signal="positive",
            )
        )
        await session.execute(
            insert(models.WORK_ITEM).values(
                work_item_id=work_item_id,
                tenant_id=tenant_id,
                session_id=session_id,
                requested_by_oid=requester,
                state=WorkItemState.EXECUTED.value,
                approval_state=ApprovalState.APPROVED.value,
            )
        )
        await session.execute(
            insert(models.AUDIT_EVENT).values(
                audit_id=uuid4(),
                tenant_id=tenant_id,
                work_item_id=work_item_id,
                occurred_at=datetime.now(UTC) - timedelta(days=200),
                action="execution.recorded",
                requested_by_oid=requester,
                executed_by="workload",
                execution_method=ExecutionMethod.WORKLOAD.value,
                outcome="succeeded",
                correlation_id="corr-1",
                retain_until=datetime.now(UTC) + timedelta(days=365 * 7),
            )
        )

    return {
        "tenant": TenantContext.from_admitted_identity(
            TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
        ),
        "session_id": session_id,
        "work_item_id": work_item_id,
    }


async def _count(session: AsyncSession, table: Any) -> int:
    return int((await session.execute(select(func.count()).select_from(table))).scalar_one())


@pytest.mark.integration
class TestEachClassIsRemovableIndependently:
    """And the one that must survive, survives."""

    async def test_expired_chat_content_is_removed(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """The session and everything hanging off it: messages, steps, feedback."""
        async with sessions() as session, session.begin():
            removed = await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        assert removed == 1
        async with sessions() as session:
            assert await _count(session, models.CHAT_SESSION) == 0
            assert await _count(session, models.MESSAGE) == 0
            assert await _count(session, models.SESSION_STEP) == 0
            assert await _count(session, models.FEEDBACK) == 0

    async def test_expiring_chat_content_leaves_the_audit_record_intact(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """**The property this file exists for** (spec FR-AUDIT-004, SC-AUDIT-002).

        The conversation is gone; what was decided in it is not.
        """
        async with sessions() as session, session.begin():
            await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        async with sessions() as session:
            assert await _count(session, models.AUDIT_EVENT) == 1

    async def test_the_audit_record_is_still_complete(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Intact is not enough; SC-AUDIT-003 asks for complete.

        The actor chain, the correlation identifier and the work item it concerns all survive — so
        the record still answers who asked, who did it, by what means, and against which case.
        """
        async with sessions() as session, session.begin():
            await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        async with sessions() as session:
            row = (await session.execute(select(models.AUDIT_EVENT))).one()

        assert row.work_item_id == organisation["work_item_id"]
        assert row.executed_by == "workload"
        assert row.execution_method is ExecutionMethod.WORKLOAD
        assert row.requested_by_oid is not None
        assert row.correlation_id == "corr-1"

    async def test_the_work_item_survives_its_conversation(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Work follows *audit* retention, not chat retention.

        ``ON DELETE RESTRICT`` on the session reference is what makes this structural — and the
        sweeper deletes the session only because the work item no longer references a live one.
        """
        async with sessions() as session, session.begin():
            await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        async with sessions() as session:
            assert await _count(session, models.WORK_ITEM) == 1

    async def test_a_live_session_is_never_swept(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Null ``content_expires_at`` means *not yet eligible*, never *overdue*."""
        async with sessions() as session, session.begin():
            await session.execute(
                update(models.CHAT_SESSION).values(
                    state=SessionState.AWAITING_APPROVAL.value, content_expires_at=None
                )
            )

        async with sessions() as session, session.begin():
            removed = await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        assert removed == 0
        async with sessions() as session:
            assert await _count(session, models.CHAT_SESSION) == 1

    async def test_a_session_inside_its_window_is_never_swept(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Terminal is not the same as expired."""
        async with sessions() as session, session.begin():
            await session.execute(
                update(models.CHAT_SESSION).values(
                    content_expires_at=datetime.now(UTC) + timedelta(days=89)
                )
            )

        async with sessions() as session, session.begin():
            removed = await sweep_chat_content(session, organisation["tenant"], datetime.now(UTC))

        assert removed == 0

    async def test_the_sweep_is_scoped_to_one_organisation(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """A defect in the predicate costs one organisation's data rather than everyone's."""
        stranger = TenantContext.from_admitted_identity(
            TenantId(uuid4()), EntraTenantId(uuid4()), TenantStatus.ACTIVE
        )

        async with sessions() as session, session.begin():
            removed = await sweep_chat_content(session, stranger, datetime.now(UTC))

        assert removed == 0
        async with sessions() as session:
            assert await _count(session, models.CHAT_SESSION) == 1


@pytest.mark.integration
class TestAuditIsBeyondTheRuntimesReach:
    """Append-only is a grant, not a rule — and retention here is somebody else's job."""

    def test_the_sweeper_module_issues_no_delete_against_audit(self) -> None:
        """Structural: the worker has no statement that could remove an audit row.

        Expiring audit past ``retain_until`` is a privileged, separately-audited job. A worker that
        *could* do it is a worker that could be made to do it early.
        """
        import ast
        from pathlib import Path

        source = Path("workers/retention_sweep.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        deleted = {
            argument.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "delete"
            for argument in node.args
            if isinstance(argument, ast.Attribute)
        }
        assert "AUDIT_EVENT" not in deleted

    async def test_an_audit_row_past_its_horizon_leaves_the_published_view(
        self, sessions: async_sessionmaker[AsyncSession], organisation: dict[str, Any]
    ) -> None:
        """Rule 4: retention is respected inside the view, not by the caller.

        The row is still in the table — removing it is not the runtime's to do — and it is already
        unreadable through the contract.
        """
        from sqlalchemy import text

        async with sessions() as session, session.begin():
            await session.execute(
                update(models.AUDIT_EVENT).values(
                    retain_until=datetime.now(UTC) - timedelta(days=1)
                )
            )

        async with sessions() as session:
            through_view = (
                await session.execute(text("SELECT count(*) FROM platform.vw_audit_event_v1"))
            ).scalar_one()
            in_table = await _count(session, models.AUDIT_EVENT)

        assert through_view == 0
        assert in_table == 1
