"""The proposed operation, and what a proposal is structurally unable to say.

**MODEL MAY PROPOSE. MODEL MAY NOT AUTHORIZE.**

That sentence is a rule in A3 §6.3 and a test in
``tests/governance/test_authority_boundary.py``. Here it is a *type*: a :class:`ProposedOperation`
names an operation and its parameters and stops. It has no ``treatment`` field, no ``approved``
flag, no ``roles`` and no ``tenant``. A model — or retrieved content, or a vendor response, or a
line of chat — that wants to authorize something has nowhere to put the claim.

The alternative design, a proposal carrying a ``treatment`` that governance is trusted to
overwrite, fails the moment one code path forgets to overwrite it. This one cannot be forgotten,
because the field it would have to read does not exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from ragcore.domain.identifiers import OperationIdentity


class ProposalSource(Enum):
    """Where a proposal came from.

    Recorded for audit and for honest reporting. **It is never consulted to decide anything**:
    a proposal from a deterministic planner and a proposal from the model reach exactly the
    same gate, because "the trustworthy component suggested it" is not an authorization and a
    system that treats it as one has a promotion path.
    """

    MODEL = "model"
    """The agent loop proposed it. The ordinary case."""

    DETERMINISTIC = "deterministic"
    """A deterministic planner proposed it. Still a proposal, still gated."""

    STAFF_REQUEST = "staff_request"
    """A staff member asked for it through an authenticated API. Still a proposal."""


@dataclass(frozen=True, slots=True)
class ProposedOperation:
    """What the agent suggests doing. **Not** a decision that it may be done.

    Deliberately absent, and never to be added:

    * ``treatment`` — assigned by :mod:`ragcore.governance.policy` from the catalogue.
    * ``approved`` / ``authorized`` — recorded on the durable work item by a human decision.
    * ``accepted_roles`` — a catalogue property; a proposal that declared its own would be
      choosing who may approve it.
    * ``tenant_id`` — derived from trusted identity or from the work item, never proposed.

    Attributes:
        identity: The catalogue entry and version the proposal names. A proposal that names
            nothing in the catalogue is refused at the gate; it does not default to permitted.
        parameters: The arguments. Read as **data**: the destination of an outbound call MUST
            NEVER be derived from these (spec FR-EXT-018) — it comes from the catalogue entry.
        source: Provenance, for audit. Never consulted by the gate.
        rationale: Free text for the approval disclosure and the step trail. Never parsed.
    """

    identity: OperationIdentity
    parameters: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    source: ProposalSource = ProposalSource.MODEL
    rationale: str = ""

    def __post_init__(self) -> None:
        """Freeze the parameter mapping so a later stage cannot edit an approved proposal.

        An approval binds what was disclosed. A mutable mapping shared with the caller would let
        the parameters change between disclosure and execution, which is precisely the swap the
        content hash on the catalogue entry exists to detect.
        """
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
