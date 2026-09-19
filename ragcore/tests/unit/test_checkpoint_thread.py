"""A checkpoint thread is keyed on trusted identity, not on the identifier a caller supplies.

The thread holds a conversation's durable state and the authority context of whatever it is
suspended on; whoever can name it can resume it. Before the triage gate no ``chat_session`` row
exists (spec FR-SESS-003), so there is nothing durable to check ownership against — the key is the
whole of the control. These tests are what make it one.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from ragcore.domain.identifiers import (
    CorrelationId,
    EntraTenantId,
    PrincipalId,
    SessionId,
    TenantId,
)
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.graph.context import RunContext
from ragcore.graph.host import thread_config
from ragcore.graph.threads import checkpoint_thread_id


def _context(tenant_id: UUID, requester: UUID, session_id: UUID) -> RunContext:
    tenant = TenantContext.from_admitted_identity(
        TenantId(tenant_id), EntraTenantId(uuid4()), TenantStatus.ACTIVE
    )
    return RunContext(
        tenant=tenant,
        requester=PrincipalId(requester),
        correlation_id=CorrelationId("0b8f7c1e-2c7a-4d51-9a55-7d0c6d8e1f00"),
        session_id=SessionId(session_id),
    )


def _thread(context: RunContext) -> str:
    return str(thread_config(context)["configurable"]["thread_id"])


class TestTheKeyIsDerivedFromTrustedIdentity:
    def test_the_same_owner_and_session_resume_the_same_thread(self) -> None:
        """A conversation must be resumable by its owner, turn after turn (FR-SESS-006)."""
        tenant, requester, session = uuid4(), uuid4(), uuid4()

        assert _thread(_context(tenant, requester, session)) == _thread(
            _context(tenant, requester, session)
        )

    def test_another_organisation_naming_the_session_reaches_a_different_thread(self) -> None:
        requester, session = uuid4(), uuid4()

        assert _thread(_context(uuid4(), requester, session)) != _thread(
            _context(uuid4(), requester, session)
        )

    def test_another_user_naming_the_session_reaches_a_different_thread(self) -> None:
        tenant, session = uuid4(), uuid4()

        assert _thread(_context(tenant, uuid4(), session)) != _thread(
            _context(tenant, uuid4(), session)
        )

    def test_the_session_identifier_alone_is_never_the_key(self) -> None:
        """The regression this file exists for: the thread used to BE the session identifier."""
        session = uuid4()

        assert _thread(_context(uuid4(), uuid4(), session)) != str(session)

    def test_the_host_and_the_retention_sweeper_agree_on_the_key(self) -> None:
        """The sweeper derives the key from the work item; the host from the run context.

        When they disagreed — the host by session, the sweeper by work item — no conversation's
        checkpoints were ever pruned.
        """
        tenant, requester, session = uuid4(), uuid4(), uuid4()

        assert _thread(_context(tenant, requester, session)) == checkpoint_thread_id(
            tenant, requester, session
        )
