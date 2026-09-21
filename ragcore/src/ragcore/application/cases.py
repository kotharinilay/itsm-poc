"""Case creation at the triage gate — **one session, exactly one case** (`FR-EXT-002`).

A session that has articulated a request is anchored to a case in the system of record. Not to
zero, and not to two.

**Why it happens at the triage gate and not earlier.** The gate is where the platform first has
something to write down. A case opened when a session opened would be a case whose short
description is "hello", and a technician's queue would fill with them. `FR-SESS-003` puts the work
record at the same moment for the same reason, and the two are created together so a work item
without a case, or a case without a work item, does not exist as a state to reason about.

**Why exactly one, and why that is enforced by an idempotency key rather than by a flag.** The
anchoring call is a write to an external system over a network, so it can succeed and be reported
as failed. A caller that retried on a "failure" would post a second case, and the two would be
indistinguishable to anybody reading the queue. The key is derived from the session identifier —
:func:`anchor_key` — so a retry of the same session's anchoring is the same key by construction. A
boolean "already anchored" field would only be correct if the write that set it always completed.

**The system of record is not an authority** (spec FR-EXT-005, FR-EXT-006). A case reference is an
identifier the platform stores and quotes. It confers no permission, carries no approval, and
nothing in this module reads a decision back out of it. :class:`~ragcore.application.ports.
CaseSystemPort` returns a receipt and never a verdict, which is what keeps that true by
construction rather than by rule.

**A queued write is neither success nor failure** (spec FR-EXT-007). When the system of record is
unreachable the write is held for replay, and :class:`CaseAnchor` reports that as its own state.
A session whose case is queued has not failed and **must not** be reported as resolved: the
platform does not yet know that the case exists, and saying otherwise would be claiming to know
more than it does (ADR-0004).

**No ServiceNow vocabulary appears here.** No ``sys_id``, no ``incident``, no table name — the
platform's own model is a case reference and facts about a session (spec FR-EXT-011).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ragcore.domain.identifiers import IdempotencyKey

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

    from ragcore.application.ports import CaseSystemPort, ClockPort
    from ragcore.domain.identifiers import CorrelationId, PrincipalId, SessionId
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "CaseAnchor",
    "CaseAnchorState",
    "CaseAnchoring",
    "anchor_key",
]


def anchor_key(session_id: SessionId) -> IdempotencyKey:
    """The idempotency key for anchoring one session to a case.

    **Derived from the session and nothing else.** Not from the clock, not from a counter, not from
    a random value — all three would produce a different key on a retry, which is precisely when
    the key has to be the same. One session anchors once, and the key is the sentence that says so.

    Args:
        session_id: The session being anchored.

    Returns:
        The key.
    """
    return IdempotencyKey(f"case.anchor:{session_id}")


class CaseAnchorState(Enum):
    """What the platform knows about the anchoring. Three states, not a boolean.

    ``QUEUED`` is why this is an enum. A boolean would force it into ``True`` or ``False``, and
    both readings are wrong: reported as success, a session could be resolved on a case nobody has
    confirmed exists; reported as failure, the platform would re-post a write that is already
    waiting to be replayed.
    """

    COMMITTED = "committed"
    """The system of record accepted the write. The case reference is real."""

    QUEUED = "queued"
    """The system was unreachable; the write is held for replay (spec FR-EXT-007).

    The session continues — the agent loop is not blocked by an unavailable external system — but
    it **may not be reported as resolved** until the case commits.
    """

    NOT_REQUIRED = "not_required"
    """Triage has not committed a work record, so there is nothing to anchor yet.

    Reported honestly as *not required* rather than as a failure, so a step trail never says a case
    could not be created when none was sought.
    """


@dataclass(frozen=True, slots=True)
class CaseAnchor:
    """The anchoring outcome for one session.

    Attributes:
        state: What the platform knows.
        case_reference: The platform's identifier for the case, once one exists. ``None`` while the
            write is queued, because a reference the platform invented for a case the system of
            record has not accepted would be a reference that resolves to nothing.
    """

    state: CaseAnchorState
    case_reference: str | None = None

    @property
    def may_report_resolution(self) -> bool:
        """Whether a session anchored this way may be reported as resolved.

        Only a committed case qualifies. A queued write means the platform does not yet know the
        case exists, and `FR-EXT-007` is explicit that a session which cannot commit its case must
        not proceed to resolution.
        """
        return self.state is CaseAnchorState.COMMITTED


@dataclass(frozen=True, slots=True)
class CaseAnchoring:
    """Anchors a session to exactly one case, at the triage gate.

    Attributes:
        cases: The single owning boundary for system-of-record traffic.
        clock: The current instant, for the facts written onto the case.
    """

    cases: CaseSystemPort
    clock: ClockPort

    async def anchor(
        self,
        tenant: TenantContext,
        session_id: SessionId,
        requester: PrincipalId,
        correlation_id: CorrelationId,
        summary: str,
    ) -> CaseAnchor:
        """Create or re-affirm the one case for this session.

        Idempotent by construction: the key comes from :func:`anchor_key`, so calling this twice
        for one session reaches the same key and the system of record recognises the repeat.

        Args:
            tenant: The organisation. Required and non-defaulted, like every port signature here.
            session_id: The session. Both the anchor and the idempotency key derive from it.
            requester: Who asked. Written onto the case as a stable principal identifier, never as
                a credential and never as a directory display name resolved for the occasion.
            correlation_id: Carried onto the write, so the case and the session's telemetry and
                audit records join on one identifier (spec FR-OPS-001).
            summary: What the user described, as the platform would quote it. **Data.** It is
                written to the case and never parsed, and nothing downstream reads it back to
                decide anything.

        Returns:
            The anchor. A queued write is reported as queued, not as a success and not as an error.
        """
        facts = self._facts(session_id, requester, correlation_id, summary)
        key = anchor_key(session_id)

        receipt = await self.cases.record_progress(
            tenant,
            # The case reference the platform quotes for a session it has not yet anchored is the
            # session's own identity. The owning boundary maps it onto whatever the external system
            # calls a record; that mapping is the adapter's, and its vocabulary stays there.
            str(session_id),
            facts,
            key,
            correlation_id,
        )

        if receipt.committed:
            return CaseAnchor(CaseAnchorState.COMMITTED, case_reference=str(session_id))
        if receipt.queued:
            return CaseAnchor(CaseAnchorState.QUEUED)

        # Neither committed nor queued. The receipt reports three states and this is the fourth
        # nobody should be able to produce; treated as queued rather than as success, because
        # every unknown on this path resolves towards "the platform does not know the case exists".
        return CaseAnchor(CaseAnchorState.QUEUED)

    def _facts(
        self,
        session_id: SessionId,
        requester: PrincipalId,
        correlation_id: CorrelationId,
        summary: str,
    ) -> Mapping[str, str]:
        """The facts written onto the case.

        Strings only, and few. **No credential, no token, no directory profile and no role.** A
        case is readable by everybody who can see the queue, which makes it the wrong place for
        anything the platform would redact from a log line.
        """
        return {
            "sessionId": str(session_id),
            "requestedByOid": str(requester),
            "correlationId": str(correlation_id),
            "openedAt": self.clock.now().isoformat(),
            "summary": summary,
            # Stated on the record rather than inferred by a reader. The scaffold's catalogue holds
            # only inert reference fixtures, and a case that did not say so would look like a case
            # about a real operation (10-principles.md H-1).
            "origin": "synthia",
        }
