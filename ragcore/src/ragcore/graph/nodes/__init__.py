"""Graph nodes, grouped by the boundary each sits on.

* :mod:`~ragcore.graph.nodes.conversation` — the turn loop and the clarification interrupt.
* :mod:`~ragcore.graph.nodes.grounding` — retrieval and proposal, where untrusted content enters.
* :mod:`~ragcore.graph.nodes.governance` — the single call into the deterministic gate.
* :mod:`~ragcore.graph.nodes.interrupts` — the consent and approval interrupts.
* :mod:`~ragcore.graph.nodes.execution` — invocation and verification.
* :mod:`~ragcore.graph.nodes.closure` — honest closure for refused and declined work.

Every node is built by a ``make_*`` factory taking :class:`~ragcore.graph.dependencies.
GraphDependencies`. There is no module-level state and nothing to reach for at runtime.
"""
