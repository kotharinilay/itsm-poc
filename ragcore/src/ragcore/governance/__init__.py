"""Treatment policy and the control gate. Deterministic only.

Five modules:

* :mod:`~ragcore.governance.catalogue` — the validated shape a catalogue entry takes once
  governance can see it, and the only place a stored row becomes one.
* :mod:`~ragcore.governance.fixtures` — the four inert reference operations, one per treatment,
  excluded from production configuration and never a use case.
* :mod:`~ragcore.governance.policy` — which of the four treatments an operation gets.
* :mod:`~ragcore.governance.conditions` — knowledge, ability and security as three independent
  conditions. **No score, no weighting**: knowledge may withhold but never authorize.
* :mod:`~ragcore.governance.gate` — whether a proposed operation proceeds, suspends or is refused.

The authority boundary itself — which sources may grant authority at all — is
:mod:`ragcore.domain.authority`, one layer further in. It sits there deliberately: ``domain/``
is proven by ``tests/architecture/test_layering.py`` to import nothing beyond the standard
library, so the rule that retrieved, fetched and chat content cannot confer authority is stated
where no infrastructure can reach it.

Nothing in this package performs I/O, reads a clock or calls a model. Catalogue data arrives
through :class:`~ragcore.application.ports.OperationCataloguePort`; the **decision** over that
data is made here and is not injectable, because an injectable decision is one an adapter could
change.
"""
