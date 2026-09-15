"""The RagCore composition root.

THE ONLY place adapters are constructed and bound to the ports they implement
(plan §Composition roots). FastAPI ``Depends`` resolves from here and constructs nothing
itself; no module outside this one instantiates a concrete adapter.

Service Locator is prohibited. A dependency that cannot be reached from this module is a
dependency nothing should be using.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Container:
    """Holds every constructed adapter, bound to the port it satisfies.

    Empty at Stage 1: there are no adapters yet. Stage 9 populates it, and the shape stays
    frozen so a caller cannot reach in and swap a binding at runtime.
    """


def build_container() -> Container:
    """Construct the container once, at application startup.

    Returns:
        The fully constructed container. Called from the FastAPI lifespan handler.
    """
    return Container()
