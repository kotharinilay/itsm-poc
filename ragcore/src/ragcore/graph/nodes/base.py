"""Shared types for graph nodes.

A node is an async callable of ``(state, runtime)``. Stating that as one alias means the builder
can hold a table of nodes that type-checks, rather than a dict of ``Callable[..., Any]`` that
would accept anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from langgraph.runtime import Runtime

from ragcore.graph.context import RunContext
from ragcore.graph.state import AgentState


class GraphNode(Protocol):
    """One node: reads state and run context, returns the channels it wrote.

    A Protocol rather than a ``Callable`` alias because LangGraph passes ``runtime`` as a
    keyword-only argument, and a ``Callable`` alias cannot express that. A node declared with
    ``runtime`` positional type-checks against the alias and then fails at run time; against
    this it fails at check time, which is where the mistake is cheap.
    """

    async def __call__(self, state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState: ...


def resume_field(payload: object, key: str) -> str:
    """Read one string field from an interrupt's resume payload.

    **The resume payload is untrusted client input.** It arrives as whatever the caller passed to
    ``Command(resume=...)``, which originates from an HTTP request body. Validating it here is
    not ceremony: a node that indexed it directly would be trusting a client-supplied structure.

    Note what this function cannot be used for. It returns text, and text carries no authority —
    no node reads a decision out of a resume payload. The consent and approval nodes re-read the
    durable record instead, which is why they take repositories and this helper does not appear
    in either.

    Args:
        payload: Whatever the client resumed with.
        key: The field to read.

    Returns:
        The field's value when it is present and a string; the empty string otherwise. A missing
        field is not an error — it is a client that sent less than expected, and a scaffold node
        has nothing to fail about.
    """
    if isinstance(payload, Mapping):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""
