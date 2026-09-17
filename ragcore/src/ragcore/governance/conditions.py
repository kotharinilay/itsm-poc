"""Knowledge, ability and security — **three independent conditions, never a score**.

`FR-AGENT-005` states the rule and states it negatively: the three MUST be evaluated as independent
conditions, **none may average away another**, and the knowledge condition **may withhold but MUST
NEVER authorize**.

**Why the negative form is the whole design.** The natural implementation of "three signals" is a
weighted score with a threshold, and a weighted score is exactly what the requirement forbids: a
confident model and a well-entitled capability would arithmetically outvote missing evidence, and
the system would act on a guess while reporting a high number. So there is no number here. Each
condition answers a boolean, the combiner in :func:`evaluate_conditions` is a conjunction, and there
is nowhere for a weight to be introduced without deleting a type.

**The asymmetry is deliberate and is the second half of the rule.** Knowledge can only ever remove
an outcome:

* knowledge insufficient → withhold, whatever the other two say;
* knowledge sufficient → *nothing*. It does not authorize, it does not upgrade a refusal, it does
  not shorten an approval requirement. Security alone authorizes, through
  :mod:`ragcore.governance.gate`.

That is why :class:`KnowledgeCondition` exposes ``withholds`` and no ``authorizes``: "confidence in
ability never substitutes for evidence; the knowledge gate may withhold but never authorize"
(spec §Edge cases).

**Knowledge uses absolute score together with margin** (`FR-AGENT-006`). A raw similarity score is
not a probability, and a top score of 0.71 means something different when the runner-up scored 0.70
than when it scored 0.31 — the first is a near-tie between two candidate answers and the second is a
confident single match. Thresholding on the top score alone cannot tell them apart, so both are
required.

**The thresholds are global platform constants, and they are not written down here**
(`FR-AGENT-007`, plan §Stage 12). Both figures and their comparison direction live in
:mod:`ragcore.retrieval.confidence` and nowhere else; this module imports them. The import
direction is deliberate: two thresholds restated in two modules are two thresholds that agree until
somebody tunes one, and the divergence that follows is invisible — retrieval would consider
evidence sufficient while the gate withheld on it, or the reverse. They are re-exported below so a
reader of this module can still see the figures that govern it, without this module becoming a
second place to change them.

Nothing here performs I/O, reads a clock or calls a model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from ragcore.retrieval.confidence import MINIMUM_MARGIN, MINIMUM_TOP_SCORE, Scored, assess

__all__ = [
    "MINIMUM_MARGIN",
    "MINIMUM_TOP_SCORE",
    "AbilityCondition",
    "ConditionKind",
    "ConditionOutcome",
    "ConditionSet",
    "KnowledgeCondition",
    "Scored",
    "SecurityCondition",
    "evaluate_conditions",
]


class ConditionOutcome(Enum):
    """What one condition concluded. Deliberately not a number.

    Two members and no third. There is no ``PARTIAL`` and no confidence value, because the moment a
    condition reports a degree, something downstream combines degrees — and a combination of degrees
    is the averaging `FR-AGENT-005` forbids.
    """

    MET = "met"
    NOT_MET = "not_met"


class ConditionKind(Enum):
    """Which of the three. Named so a withholding decision can say which condition withheld."""

    KNOWLEDGE = "knowledge"
    """Is there evidence to act on? May withhold; never authorizes."""

    ABILITY = "ability"
    """Can the platform perform this at all — registered, entitled, and a capability it holds?"""

    SECURITY = "security"
    """Is it authorized — deterministic treatment, and any human decision it requires?"""


@dataclass(frozen=True, slots=True)
class KnowledgeCondition:
    """Whether there is evidence worth acting on.

    Attributes:
        outcome: Met or not. Never a degree.
        top_score: The best candidate's absolute score, for the audit record and the step trail.
        margin: The gap to the runner-up, or the top score itself when there is no runner-up.
        required: Whether this operation needed grounding at all. ``False`` for an operation that
            acts on platform state rather than on retrieved knowledge — and an operation that needs
            no evidence is not thereby *better* evidenced, which is why this is a separate field
            rather than an outcome of ``MET``.
    """

    outcome: ConditionOutcome
    top_score: float
    margin: float
    required: bool

    @property
    def withholds(self) -> bool:
        """Whether this condition blocks the operation.

        **The only question this type answers.** There is deliberately no ``authorizes``: knowledge
        that is present does not permit anything, and a property saying otherwise would eventually
        be read by something looking for a reason to proceed.
        """
        return self.required and self.outcome is ConditionOutcome.NOT_MET

    @classmethod
    def not_required(cls) -> KnowledgeCondition:
        """For an operation that acts on platform state rather than on retrieved knowledge.

        Reported honestly as *not required* rather than as met, so an audit record never says
        evidence was found where none was sought.
        """
        return cls(ConditionOutcome.MET, top_score=0.0, margin=0.0, required=False)

    @classmethod
    def assess(cls, chunks: Sequence[Scored]) -> KnowledgeCondition:
        """Assess grounding from retrieved evidence.

        The two comparisons are :func:`ragcore.retrieval.confidence.assess`'s, not this module's.
        What is added here is the *meaning*: a confident assessment becomes ``MET``, which permits
        nothing on its own, and an unconfident one becomes ``NOT_MET``, which withholds.

        Args:
            chunks: The retrieved chunks, in any order. Ordering is not trusted — see
                :func:`~ragcore.retrieval.confidence.assess_scores`, which sorts.

        Returns:
            The condition. Empty evidence is **not met** — an absence of evidence is not a weak
            positive, and it is the case where a scored implementation is most likely to return
            something that passes a threshold by default.
        """
        confidence = assess(chunks)
        return cls(
            ConditionOutcome.MET if confidence.is_confident else ConditionOutcome.NOT_MET,
            top_score=confidence.top_score,
            margin=confidence.margin,
            required=True,
        )


@dataclass(frozen=True, slots=True)
class AbilityCondition:
    """Whether the platform can perform this operation at all.

    Registration and entitlement, which are two facts and not one: a capability is callable only
    when registered in the catalogue **and** entitled to the organisation, and discovery never
    confers entitlement (spec FR-EXT-014, FR-EXT-015).

    Attributes:
        outcome: Met or not.
        is_registered: Whether a catalogue entry exists.
        is_entitled: Whether this organisation may call it.
    """

    outcome: ConditionOutcome
    is_registered: bool
    is_entitled: bool

    @classmethod
    def assess(cls, *, is_registered: bool, is_entitled: bool) -> AbilityCondition:
        """Assess ability from the two independent facts."""
        met = is_registered and is_entitled
        return cls(
            ConditionOutcome.MET if met else ConditionOutcome.NOT_MET,
            is_registered=is_registered,
            is_entitled=is_entitled,
        )


@dataclass(frozen=True, slots=True)
class SecurityCondition:
    """Whether the operation is authorized.

    **This is the only condition that can authorize anything**, and it does so through
    :func:`ragcore.governance.gate.evaluate` — deterministic treatment from the catalogue plus any
    human decision that treatment requires.

    Attributes:
        outcome: Met or not.
        is_authorized: Whether the gate said proceed. Taken from a
            :class:`~ragcore.governance.gate.GateOutcome`, never constructed beside one.
    """

    outcome: ConditionOutcome
    is_authorized: bool

    @classmethod
    def assess(cls, *, is_authorized: bool) -> SecurityCondition:
        """Assess security from the gate's own conclusion."""
        return cls(
            ConditionOutcome.MET if is_authorized else ConditionOutcome.NOT_MET,
            is_authorized=is_authorized,
        )


@dataclass(frozen=True, slots=True)
class ConditionSet:
    """All three, evaluated independently, with the reason the combination concluded what it did.

    Attributes:
        knowledge: May withhold; never authorizes.
        ability: Registered and entitled.
        security: The gate's conclusion.
    """

    knowledge: KnowledgeCondition
    ability: AbilityCondition
    security: SecurityCondition

    @property
    def proceeds(self) -> bool:
        """Whether all three permit the operation to go ahead.

        **A conjunction, and there is nowhere to put a weight.** Every operand is a boolean, so a
        strong result on one condition cannot compensate for a failure on another — which is the
        whole of `FR-AGENT-005`'s "none may average away another", expressed as the absence of
        arithmetic rather than as a comment asking for it.
        """
        return (
            self.security.is_authorized
            and self.ability.outcome is ConditionOutcome.MET
            and not self.knowledge.withholds
        )

    @property
    def withheld_by(self) -> tuple[ConditionKind, ...]:
        """Which conditions blocked, in evaluation order. Empty when the operation proceeds.

        Every condition that failed, not the first: an operation that is both ungrounded and
        unentitled has two things wrong with it, and reporting one would send somebody to fix half.
        """
        blocked: list[ConditionKind] = []

        if self.knowledge.withholds:
            blocked.append(ConditionKind.KNOWLEDGE)
        if self.ability.outcome is ConditionOutcome.NOT_MET:
            blocked.append(ConditionKind.ABILITY)
        if not self.security.is_authorized:
            blocked.append(ConditionKind.SECURITY)

        return tuple(blocked)


def evaluate_conditions(
    *,
    knowledge: KnowledgeCondition,
    ability: AbilityCondition,
    security: SecurityCondition,
) -> ConditionSet:
    """Combine the three conditions without combining them.

    Keyword-only, and every argument required. A positional call could silently swap two conditions
    of the same shape, and there is no default for any of them — a missing condition would have to
    default to something, and both possible defaults are wrong: permissive defaults authorize by
    omission, and restrictive ones make a caller that forgot look like a caller that was refused.

    Args:
        knowledge: Whether there is evidence. May withhold; never authorizes.
        ability: Whether the platform can perform this at all.
        security: Whether the gate authorized it.

    Returns:
        The three, independently, with the combination's verdict derived rather than stored.
    """
    return ConditionSet(knowledge=knowledge, ability=ability, security=security)
