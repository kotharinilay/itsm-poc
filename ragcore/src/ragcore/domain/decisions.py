"""Recorded human decisions, as read back from the durable record.

Two types, not one. **Consent MUST NOT satisfy a requirement for staff approval**
(spec FR-INTR-007), and with separate types that rule is enforced by the gate's branches
accepting only the right one — rather than by a ``kind`` comparison somebody could omit.

These live in the domain rather than beside the gate because
:mod:`ragcore.application.ports` declares the repositories that return them, and a port declared
in terms of a governance type would invert the dependency direction.

**Nothing here is constructible from a message.** Each type names the durable row it came from,
and the resume worker reads that row rather than believing the trigger that woke it: every
trigger is untrusted, and the work record provides the authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ragcore.domain.authority import AuthoritySource
from ragcore.domain.identifiers import ApprovalId, ConsentId, OperationIdentity, PrincipalId
from ragcore.domain.roles import RoleSet
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict


@dataclass(frozen=True, slots=True)
class StaffVerdict:
    """A staff decision, as read back from the durable approval record.

    Attributes:
        approval_id: The approval row this decided.
        decided_by: The staff principal. Bound at decision time and never reassigned.
        roles_held: The role set held **at the moment of decision** (spec FR-AUTHZ-011). Stored
            rather than re-resolved, because a role granted or revoked afterwards must not
            retroactively change whether a past decision was valid.
        verdict: ``APPROVED`` or ``REJECTED``. Two members — there is no ``EXPIRED`` to pass, so
            a system-synthesized verdict is unrepresentable rather than merely prohibited
            (spec FR-INTR-008).
        bound_to: The operation identity, including its catalogue version, that the approver saw.
            A catalogue edit between approval and execution changes this and the gate refuses.
        decided_at: When the decision was recorded.
        expires_at: When the execution validity window closes — ``decided_at`` plus fifteen
            minutes (data-model.md ``approval.expires_at``). Read from the durable row, never
            computed here: a window this type calculated would be a second answer to "until
            when", and the row would stop being the authority. ``None`` where no window has been
            opened, which the gate treats as a refusal rather than as unlimited.
        source: Fixed. Present so the audit record names where the authority came from.
    """

    approval_id: ApprovalId
    decided_by: PrincipalId
    roles_held: RoleSet
    verdict: ApprovalVerdict
    bound_to: OperationIdentity
    decided_at: datetime
    expires_at: datetime | None = None
    source: AuthoritySource = AuthoritySource.AUTHENTICATED_STAFF_VERDICT


@dataclass(frozen=True, slots=True)
class EndUserConsent:
    """The requester's own consent, as read back from the durable consent record.

    Attributes:
        consent_id: The consent row.
        consented_by: Must be the work item's own requester. The caller establishes that; this
            type carries it so the gate re-checks rather than trusts.
        verdict: ``GRANTED`` or ``REFUSED``.
        bound_to: The operation identity and version the requester was shown.
        decided_at: When the decision was recorded.
        expires_at: When the execution validity window closes. Fifteen minutes applies to a
            granted consent exactly as it does to an approval. ``consent`` has no such column of
            its own in data-model.md — the work item holds it — so the repository resolves it
            from there and returns it here. Same rule either way: read, never computed.
        source: Fixed. Present so the audit record names where the authority came from.
    """

    consent_id: ConsentId
    consented_by: PrincipalId
    verdict: ConsentVerdict
    bound_to: OperationIdentity
    decided_at: datetime
    expires_at: datetime | None = None
    source: AuthoritySource = AuthoritySource.AUTHENTICATED_END_USER_CONSENT


RecordedDecision = StaffVerdict | EndUserConsent
"""A decision that actually happened. Read from the durable record, never from a message."""
