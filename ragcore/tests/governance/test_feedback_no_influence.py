"""T187 — feedback reaches **no authorization, no governance treatment, no retrieval scope and no
execution path** (`FR-SESS-013`).

The difficulty with testing a negative like this is that the obvious test — record some feedback,
assert the gate says the same thing — passes trivially against an implementation that reads
feedback and happens not to be influenced by the two values tried. So the assertions below are
mostly **structural**: they walk the source and assert that the decision-making modules do not
import, mention or hold a feedback type at all.

A structural assertion is the right shape here because the requirement is itself structural. It is
not "feedback should not usually change a decision"; it is that feedback is a quality signal and
the decision path has no way to read one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "ragcore"

DECISION_MODULES = (
    "governance/gate.py",
    "governance/policy.py",
    "governance/conditions.py",
    "governance/catalogue.py",
    "domain/roles.py",
    "domain/authority.py",
    "domain/decisions.py",
    "domain/proposal.py",
    "execution/executor.py",
    "execution/claim.py",
    "execution/idempotency.py",
    "retrieval/search.py",
    "retrieval/hybrid.py",
    "retrieval/rerank.py",
    "retrieval/confidence.py",
    "graph/nodes/governance.py",
    "graph/nodes/execution.py",
    "graph/nodes/classify.py",
    "graph/nodes/grounding.py",
)
"""Everything that decides whether something may happen, or decides what is retrieved.

Listed explicitly rather than matched by a pattern, so adding a decision module is a deliberate
line here — and so a new one that quietly reads feedback fails this file rather than slipping
through a glob that did not match it.
"""


class TestNoDecisionModuleCanSeeFeedback:
    """Not "does not use it" — **cannot reach it**."""

    @pytest.mark.parametrize("module", DECISION_MODULES)
    def test_the_module_imports_nothing_about_feedback(self, module: str) -> None:
        path = SRC / module
        assert path.exists(), f"{module} is listed here but does not exist"

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.extend(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if "feedback" in f"{node.module}.{alias.name}".lower()
                )
            elif isinstance(node, ast.Import):
                imported.extend(
                    alias.name for alias in node.names if "feedback" in alias.name.lower()
                )

        assert not imported, (
            f"{module} imports a feedback type: {imported}. Feedback is a quality signal and MUST "
            "NOT be an input to a decision (spec FR-SESS-013)."
        )

    @pytest.mark.parametrize("module", DECISION_MODULES)
    def test_the_module_reads_no_attribute_named_for_feedback(self, module: str) -> None:
        """Catches the case an import check misses: a duck-typed row with a ``signal`` column."""
        tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
        reads = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr.lower() in {"feedback", "signal", "thumbs", "rating"}
        }

        assert not reads, f"{module} reads {sorted(reads)}"


class TestTheGateHasNowhereToPutIt:
    """A request type with no field for feedback cannot be influenced by one."""

    def test_the_gate_request_has_no_feedback_field(self) -> None:
        from ragcore.governance.gate import GateRequest

        fields = set(GateRequest.__dataclass_fields__)
        assert not {field for field in fields if "feedback" in field or "signal" in field}

    def test_the_gate_outcome_has_no_feedback_field(self) -> None:
        from ragcore.governance.gate import GateOutcome

        fields = set(GateOutcome.__dataclass_fields__)
        assert not {field for field in fields if "feedback" in field or "signal" in field}

    def test_the_graph_state_has_no_feedback_channel(self) -> None:
        """A channel would be somewhere for a node to write one, and somewhere to read it."""
        from ragcore.graph.state import AgentState

        channels = set(AgentState.__annotations__)
        assert not {channel for channel in channels if "feedback" in channel}

    def test_the_graph_dependencies_hold_no_feedback_repository(self) -> None:
        """The graph is bound to what it may consult. Feedback is not on the list."""
        from ragcore.graph.dependencies import GraphDependencies

        assert not {
            field for field in GraphDependencies.__dataclass_fields__ if "feedback" in field
        }


class TestThePortOffersNoWayBackIn:
    """Write and withdraw, and no reader."""

    def test_the_feedback_port_has_no_read_method(self) -> None:
        """A reader is the first thing a future change would reach for.

        The read side is the published ``vw_message_feedback_v1`` view, consumed by reporting —
        which is a different deployable with a different purpose, and cannot reach the gate.
        """
        from ragcore.application.ports import FeedbackRepositoryPort

        methods = {
            name
            for name in dir(FeedbackRepositoryPort)
            if not name.startswith("_") and callable(getattr(FeedbackRepositoryPort, name, None))
        }
        assert methods == {"record", "withdraw"}

    def test_the_repository_has_no_read_method_either(self) -> None:
        from ragcore.persistence.repositories import FeedbackRepository

        public = {
            name
            for name in vars(FeedbackRepository)
            if not name.startswith("_") and callable(vars(FeedbackRepository)[name])
        }
        assert public == {"record", "withdraw"}


class TestTheApiSurfaceCarriesNoDecision:
    """Recording feedback returns no outcome, because it causes none."""

    def test_the_feedback_request_has_one_field_and_it_is_a_signal(self) -> None:
        from ragcore.api.customer.feedback import FeedbackRequest

        assert set(FeedbackRequest.model_fields) == {"signal"}

    def test_the_feedback_signal_enum_has_exactly_two_members(self) -> None:
        """Two values and no third. A third would be a scale, and a scale is a score."""
        from ragcore.domain.work import FeedbackSignal

        assert {member.value for member in FeedbackSignal} == {"positive", "negative"}
