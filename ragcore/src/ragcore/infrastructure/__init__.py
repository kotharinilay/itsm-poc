"""Adapters: the outer layer, implementing ports declared by their consumers.

Dependency direction points inward. Nothing in :mod:`ragcore.domain` or
:mod:`ragcore.application` imports anything here, and ``tests/architecture/test_layering.py``
asserts that.

Almost empty in the scaffold, on purpose. The one adapter present is
:class:`~ragcore.infrastructure.clock.SystemClock`, which needs no infrastructure to construct.
Everything else — persistence, messaging, integrations — arrives at Stages 7 to 9, and until then
:class:`~ragcore.config.composition.Container` binds ``None`` rather than a convenient default
that would let the platform look like it works.
"""
