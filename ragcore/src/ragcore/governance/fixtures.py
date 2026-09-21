"""The four inert reference operations. **Scaffold fixtures, never product capability.**

`H-2` permits inert reference operations so governance paths are exercisable before a real
capability is defined. One per execution treatment, so the catalogue is
populated and deterministic treatment classification is *exercisable* before any use case exists.
`H-2` also says what they may never become.

**What "inert" means here, precisely.** Not "not wired up yet" — that would be a fixture waiting to
become real. These four have no external system, no command that reaches one, and no verification
tool, because there is nothing to verify against. The command payload each one discloses describes
a no-op, and is disclosed **in full** exactly as a real operation's would be, because the disclosure
machinery is one of the things having a populated catalogue is meant to exercise.

**Why four rather than one.** The interesting property of deterministic treatment assignment is that
it distinguishes: an ``AUTO`` operation proceeds, an ``END_USER_APPROVAL`` one suspends for the
requester, a ``STAFF_APPROVAL`` one suspends for staff, and a ``NOT_ALLOWED`` one is refused and is
never surfaced as approvable. A catalogue holding one entry exercises the lookup and none of the
distinctions.

**They are excluded from production configuration, and the exclusion is enforced.**
:func:`reference_fixtures` refuses to hand them out in a production environment rather than
documenting that somebody should not install them. Note what this is and is not: it decides whether
rows are *installed*, never what a row *means*. No treatment, role or entitlement varies by
environment, because a control that behaves differently in production is a control nobody has
exercised (see ``config/settings.py``).

**And they are never a real defined capability.** Every identifier below carries
:data:`REFERENCE_PREFIX`, every record carries ``is_reference_fixture=True``, and
``tests/governance/test_fixtures_excluded.py`` asserts both — because a fixture quietly promoted to
a real capability is the specific way this stops being honest
(`.claude/rules/10-principles.md` H-2).
"""

from __future__ import annotations

import hashlib
import json
from typing import Final

from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import OperationIdentity
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.governance.catalogue import Catalogue, CatalogueRecord

REFERENCE_PREFIX: Final = "synthia.reference."
"""Every fixture identifier starts with this. A use case never may.

A naming rule is not the control — ``is_reference_fixture`` is — but it means a fixture is
recognisable in a log line, an audit record and a queue entry without a catalogue lookup.
"""

PRODUCTION_ENVIRONMENT: Final = "production"


class ReferenceFixtureInProductionError(RuntimeError):
    """Something asked for the scaffold fixtures in a production environment.

    `H-2` excludes them from production configuration. Raised rather than returning an
    empty catalogue: a caller that silently received nothing would install nothing and report
    success, and the next person would have to work out whether the fixtures were excluded or the
    seeding step was broken.
    """


def _content_hash(commands: dict[str, object]) -> str:
    """A stable hash of a disclosed command set.

    **This is the binding between what an approver saw and what would run.** Computed over the
    canonical JSON rendering — sorted keys, no insignificant whitespace — so the same command set
    hashes identically on every machine and in every process. A hash that varied with dictionary
    ordering would fail an approval that nobody changed.
    """
    canonical = json.dumps(commands, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fixture(
    name: str,
    *,
    treatment: ExecutionTreatment,
    kind: CapabilityKind,
    risk_tier: RiskTier,
    accepted_roles: RoleSet,
    effect: str,
) -> CatalogueRecord:
    """Build one fixture.

    Args:
        name: The suffix after :data:`REFERENCE_PREFIX`.
        treatment: The treatment this fixture exists to exercise.
        kind: Whether it reads or acts. An action that does nothing is still an action: the
            execution path's audit obligations follow from the kind, not from the effect.
        risk_tier: Restricted to the two non-destructive tiers the catalogue may hold today; the
            destructive taxonomy is an open ADR-0004 item and a tier naming destruction before it
            existed would be a label with no agreed meaning.
        accepted_roles: Who may approve. Empty denies everyone, which is correct for the treatments
            where nobody is asked.
        effect: The disclosed description, written for an approver to read.
    """
    commands: dict[str, object] = {
        "operation": "no-op",
        "effect": effect,
        "externalSystem": None,
        "reversible": True,
    }

    return CatalogueRecord(
        identity=OperationIdentity(f"{REFERENCE_PREFIX}{name}", 1),
        treatment=treatment,
        accepted_roles=accepted_roles,
        kind=kind,
        risk_tier=risk_tier,
        is_reference_fixture=True,
        commands=commands,
        content_hash=_content_hash(commands),
        # NOT AN OVERSIGHT. Verification is a server-side read against the real state an operation
        # changed, and these change none. Leaving a tool name here would claim a confirmation the
        # platform could not perform: a client-reported result is a claim, not proof (ADR-0004),
        # and the platform MUST NOT claim to know more than it does.
        verification_tool=None,
    )


ECHO: Final = _fixture(
    "echo",
    treatment=ExecutionTreatment.AUTO,
    kind=CapabilityKind.READ,
    risk_tier=RiskTier.INFORMATIONAL,
    # A read on the customer surface. Nobody approves an AUTO operation, so there is no role set to
    # declare — and declaring one anyway would suggest somebody is being asked.
    accepted_roles=RoleSet(),
    effect="Returns a fixed value. Reads nothing and changes nothing.",
)
"""``AUTO`` — proceeds with no human decision. The treatment the gate lets straight through."""


SELF_SERVICE_NOTE: Final = _fixture(
    "self-service-note",
    treatment=ExecutionTreatment.END_USER_APPROVAL,
    kind=CapabilityKind.ACTION,
    risk_tier=RiskTier.LOW_IMPACT,
    # Consent comes from the requester as a person, not from a role they hold. The set is empty
    # because no role is consulted on this path at all — see the gate's consent branch, which
    # compares the consenting principal to the work item's requester and nothing else.
    accepted_roles=RoleSet(),
    effect="Would annotate the requester's own record. Annotates nothing.",
)
"""``END_USER_APPROVAL`` — suspends for the requester's own consent, indefinitely."""


STAFF_NOTE: Final = _fixture(
    "staff-note",
    treatment=ExecutionTreatment.STAFF_APPROVAL,
    kind=CapabilityKind.ACTION,
    risk_tier=RiskTier.LOW_IMPACT,
    # `technician` is the role that may approve in the initial release. `administrator` is absent
    # and its absence is the point: roles are disjoint capability sets, so an administrator does
    # not approve by implication (spec FR-AUTHZ-003).
    accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
    effect="Would annotate a platform record on the organisation's behalf. Annotates nothing.",
)
"""``STAFF_APPROVAL`` — suspends for a verdict from a holder of an accepted role."""


WITHHELD: Final = _fixture(
    "withheld",
    treatment=ExecutionTreatment.NOT_ALLOWED,
    kind=CapabilityKind.ACTION,
    risk_tier=RiskTier.LOW_IMPACT,
    # Empty, and it has to be. An entry that named an approver while being NOT_ALLOWED would be
    # describing somebody who could decide, and the whole point of this treatment is that the
    # operation is not askable: it is recorded as a denial and never surfaced as approvable.
    accepted_roles=RoleSet(),
    effect="Refused at the gate. Never surfaced as approvable, and never executed.",
)
"""``NOT_ALLOWED`` — refused, and **not** askable. The treatment with no path to a human."""


REFERENCE_FIXTURES: Final = Catalogue.of(ECHO, SELF_SERVICE_NOTE, STAFF_NOTE, WITHHELD)
"""The four, as a catalogue. One per treatment; there is no fifth and no variant."""


def reference_fixtures(environment: str) -> Catalogue:
    """The reference fixtures, for every environment that may hold them.

    Args:
        environment: ``Settings.environment`` — where this process is running.

    Returns:
        The four fixtures.

    Raises:
        ReferenceFixtureInProductionError: In a production environment. `H-2` excludes them from
            production configuration, and this is where the exclusion happens rather than in a
            runbook step somebody follows.
    """
    if environment == PRODUCTION_ENVIRONMENT:
        raise ReferenceFixtureInProductionError(
            "the reference fixtures are reference fixtures and are excluded from production "
            "configuration (10-principles.md H-2). They are not product capability and must never "
            "be presented to a user as any."
        )

    return REFERENCE_FIXTURES


def is_reference_operation(identity: OperationIdentity) -> bool:
    """Whether an identity names a scaffold fixture.

    Answered from the **identifier**, so a caller holding nothing but an identity — an audit
    record, a queue entry, a log line — can still tell. The authoritative answer is the catalogue
    entry's ``is_reference_fixture``; this is the cheap one, and
    ``tests/governance/test_fixtures_excluded.py`` asserts the two never disagree.
    """
    return identity.catalogue_id.startswith(REFERENCE_PREFIX)
