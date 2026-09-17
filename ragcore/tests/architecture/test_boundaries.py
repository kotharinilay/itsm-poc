"""Every named boundary exists, and each one is where the plan says it is.

Boundaries are mandatory even when responsibilities deploy together, and MUST NOT be collapsed
for implementation convenience (constitution Principle V). A boundary that exists only in a
diagram erodes; this file is what makes each one a fact about the tree.

The manifest below is the union of the plan's ``ragcore/`` structure and the twelve bounded
contexts. Two entries are deliberately **not** packages, and the reason is recorded against each:
collapsing them into one would lose the distinction, and spreading them into a package would
invite an implementation that consults infrastructure.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "ragcore"

PACKAGE_BOUNDARIES = {
    "api": "HTTP transport. Three audiences, no business policy.",
    "application": "Use cases and the ports adapters implement.",
    "graph": "LangGraph orchestration: typed state, nodes, three interrupts, checkpointer.",
    "governance": "Deterministic treatment policy and the control gate.",
    "retrieval": "Grounding evidence. Mandatory, non-bypassable tenant filter.",
    "execution": "Atomic claim, idempotency, invocation, verification.",
    "persistence": "Models, repositories, unit of work. Every query applies tenant_id.",
    "messaging": "Transactional outbox, publisher, resume consumer.",
    "notifications": "Realtime delivery. A leaf on every consequential path, never a link.",
    "integrations": "Adapters. No provider type reaches inward.",
    "ingestion": "The twelfth context. Acquisition through indexing.",
    "observability": "Traces, metrics, structured logs. Never a substitute for audit.",
    "infrastructure": "Adapters for the ports the inner layers declare.",
    "config": "Pydantic Settings and the composition root.",
    "domain": "Pure model. No I/O, no imports beyond the standard library.",
}

MODULE_BOUNDARIES = {
    "domain/authority.py": "The authority boundary: which sources may grant authority at all.",
    "domain/decisions.py": "Recorded human decisions, read from the durable record.",
    "domain/proposal.py": "The proposed operation — and what a proposal cannot say.",
    "domain/audit.py": "The actor chain and what a recordable event is.",
    "domain/session_state.py": "The session state machine. Nine states, one transition table.",
    "governance/catalogue.py": "The validated shape of a catalogue entry. A row becomes one here.",
    "governance/fixtures.py": "The four inert reference operations. Never product capability.",
    "governance/policy.py": "Which of the four treatments an operation gets.",
    "governance/conditions.py": "Knowledge, ability and security as three independent conditions.",
    "governance/gate.py": "Whether a proposal proceeds, suspends or is refused.",
    "graph/state.py": "The explicitly typed LangGraph state.",
    "graph/checkpointer.py": "The one durable checkpoint store.",
    "application/ports.py": "Every port, declared in domain terms.",
    "application/cancellation.py": "Cancellation-safety helpers.",
    "application/sessions.py": "The session lifecycle and the triage gate.",
    "application/cases.py": "One session, exactly one case, anchored at the triage gate.",
    "application/audit.py": "Requester, approver, executor, method, organisation and result.",
    "application/escalation.py": "Hand the request to a person, with the reason the user is told.",
    "retrieval/confidence.py": "The two thresholds, and the only place either one is written down.",
    "retrieval/hybrid.py": "A dense leg and a load-bearing sparse lexical leg, fused by weight.",
    "retrieval/rerank.py": "Cost-gated rerank: few candidates, and only plausible ones.",
    "retrieval/embedding.py": "The symptom or description field, and nothing else.",
    "execution/executor.py": "What was attempted, and separately what the platform knows.",
    "integrations/model/safety.py": "Content safety on both crossings, at one seam.",
    "graph/host.py": "The one place a compiled graph is invoked.",
    "graph/nodes/intake.py": "Where a turn becomes conversation, and where triage sits.",
    "graph/nodes/classify.py": "Classification reports; it never authorizes.",
    "graph/nodes/guardrail.py": "Decline what is not ITSM; route what cannot be answered.",
    "graph/nodes/clarification_interrupt.py": "Interrupt 1 of 3, and why it may read its resume.",
    "api/customer/sessions.py": "The conversation surface. Streams; carries no authority.",
    "api/customer/answers.py": "Answering a clarifying question. An answer decides nothing.",
    "api/customer/feedback.py": "An idempotent, owner-scoped, decision-free quality signal.",
}


class TestEveryBoundaryExists:
    """Presence, asserted per boundary so a failure names the one that went missing."""

    @pytest.mark.parametrize("package", sorted(PACKAGE_BOUNDARIES))
    def test_the_package_exists_and_is_documented(self, package: str) -> None:
        path = SRC / package
        assert path.is_dir(), f"the {package!r} boundary is missing"
        init = path / "__init__.py"
        assert init.exists(), f"{package!r} is not a package"
        assert ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))), (
            f"{package}/__init__.py has no docstring. A boundary that does not say what it is "
            "for is a directory."
        )

    @pytest.mark.parametrize("module", sorted(MODULE_BOUNDARIES))
    def test_the_module_exists_and_is_documented(self, module: str) -> None:
        path = SRC / module
        assert path.exists(), f"the {module!r} boundary is missing"
        assert ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))


class TestTwoBoundariesAreDeliberatelyNotPackages:
    """Audit and authorization, and why each sits where it does."""

    def test_audit_is_a_port_and_a_domain_type_not_a_package(self) -> None:
        """**Telemetry MUST NEVER answer an audit question** (spec FR-OPS-004).

        Audit is a boundary — a distinct port, distinct types, distinct retention — but not a
        package of its own, because it has no implementation to hold: the shape is in
        ``domain/audit.py``, the contract is ``AuditSinkPort``, and the adapter is persistence's.
        A package would suggest a third place for audit logic to accumulate.

        What it must *not* be is a logger with a flag, which is one sampling configuration away
        from losing the record.
        """
        assert (SRC / "domain" / "audit.py").exists()
        assert not (SRC / "audit").exists()

        ports = (SRC / "application" / "ports.py").read_text(encoding="utf-8")
        assert "class AuditSinkPort" in ports

        observability = (SRC / "observability" / "__init__.py").read_text(encoding="utf-8")
        assert "AuditSink" not in observability

    def test_authorization_is_a_pure_function_not_a_port(self) -> None:
        """``domain.roles.evaluate`` needs no database, no clock and no configuration.

        Making it a port would invite an implementation that consults one — and the moment it
        can, a role or a treatment can arrive from somewhere that is not the catalogue.
        """
        roles = (SRC / "domain" / "roles.py").read_text(encoding="utf-8")
        assert "def evaluate(" in roles

        ports = ast.parse((SRC / "application" / "ports.py").read_text(encoding="utf-8"))
        declared = {node.name for node in ast.walk(ports) if isinstance(node, ast.ClassDef)}
        assert not declared & {"AuthorizationPort", "GovernancePort", "TreatmentPort", "GatePort"}


class TestDependsIsConfinedToTheTransportBoundary:
    """FastAPI ``Depends`` at HTTP boundaries, and nowhere else."""

    def test_only_deps_and_routers_reference_depends(self) -> None:
        """Application services stay independently testable, without a web framework.

        A ``Depends`` default deeper in would make a service constructible only by FastAPI, and
        the unit test for it would need an app.

        Checked against the AST rather than the source text: several modules *discuss* ``Depends``
        in a docstring precisely to say where it belongs, and a substring search would flag the
        explanation along with the thing it rules out.
        """
        users = {
            str(path.relative_to(SRC)).replace("\\", "/")
            for path in sorted(SRC.rglob("*.py"))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Name) and node.id == "Depends"
        }
        assert all(user.startswith("api/") for user in users), sorted(users)

    def test_no_module_outside_the_composition_root_constructs_an_adapter(self) -> None:
        """The composition root is the only place adapters are constructed (plan §Composition).

        Service Locator is prohibited, and this is the structural half of that: a dependency not
        reachable from ``composition.py`` is a dependency nothing should be using.
        """
        adapters = {
            "SystemClock",
            # Stage 7. Listed individually rather than matched by a naming convention, so adding a
            # repository is a deliberate line in this set — and constructing one anywhere but the
            # composition root fails here rather than quietly working.
            "TenantRegistry",
            "WorkItemRepository",
            "SessionRepository",
            "ApprovalRepository",
            "ConsentRepository",
            "OperationRepository",
            "OperationCatalogue",
            "IdempotencyStore",
            "Outbox",
            "AuditSink",
            "EntitlementCredentials",
            # Stage 9. The integration adapters, on the same terms: each is a deliberate line
            # here, and constructing one outside the composition root fails rather than quietly
            # working. The model egress implementations are listed because the choice between them
            # is the single-egress rule — a selection made at a call site would be a per-caller
            # model egress.
            "AiGatewayEgress",
            "LocalDevelopmentEgress",
            "GatewayModelAdapter",
            "AzureAiSearchRetrieval",
            "ServiceNowAdapter",
            "MicrosoftGraphAdapter",
            "McpToolClient",
            "HttpClientFactory",
            "TenantCredentialResolver",
        }
        users = {
            str(path.relative_to(SRC)).replace("\\", "/")
            for path in sorted(SRC.rglob("*.py"))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in adapters
        }
        assert users <= {"config/composition.py"}


class TestTheStateCoversTheSpecifiedChannels:
    """The seven things the graph state must be prepared for."""

    def test_all_seven_channels_are_declared(self) -> None:
        """Conversation, retrieved context, proposed operation, governance result, approval,
        execution, verification.
        """
        from ragcore.graph.state import AgentState

        channels = set(AgentState.__annotations__)
        assert {
            "conversation",
            "retrieved",
            "proposal",
            "governance",
            "decision",
            "execution",
            "verification",
        } <= channels

    def test_the_three_interrupts_are_wired(self) -> None:
        """Clarification, consent, approval — each a node with an edge, not a comment."""
        from ragcore.graph.builder import build_graph
        from ragcore.graph.nodes import conversation, interrupts
        from ragcore.graph.state import AgentState
        from tests.support.fakes import build_harness

        graph = build_graph(build_harness().deps)
        nodes = set(graph.nodes)

        assert {conversation.CLARIFY, interrupts.AWAIT_CONSENT, interrupts.AWAIT_APPROVAL} <= nodes
        assert AgentState.__annotations__["pending_interrupt"] is not None
