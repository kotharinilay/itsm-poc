"""Knowledge retrieval is confined to one organisation, **structurally**.

Organisation scope is enforced at every layer, including knowledge retrieval, where filtering MUST
be mandatory and non-bypassable (spec FR-IDENT-008) — and retrieval MUST NOT return content
belonging to another organisation **under any circumstances, including deliberately crafted input**
(spec FR-IDENT-009).

``tests/integrations/test_adapters.py`` asserts the *behaviour*: the filter that goes on the wire
and the rejection of a foreign document. This file asserts the *shape*, by reading the source —
because the behavioural test can only exercise the paths that exist, and the property being claimed
is that an unfiltered path does not exist at all. A method with an optional filter parameter would
pass every behavioural test in the suite until the day something passed ``None``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from ragcore.retrieval.search import AzureAiSearchRetrieval, tenant_filter
from tests.support.fakes import admitted_tenant

SEARCH_MODULE: Final = (
    Path(__file__).resolve().parents[2] / "src" / "ragcore" / "retrieval" / "search.py"
)


def _methods() -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(SEARCH_MODULE.read_text(encoding="utf-8"), filename=str(SEARCH_MODULE))
    retrieval = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == AzureAiSearchRetrieval.__name__
    )
    return {
        node.name: node
        for node in retrieval.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


class TestThereIsNoUnfilteredQueryPath:
    """The control is the absence of a way to express one."""

    def test_search_requires_a_tenant_context_with_no_default(self) -> None:
        """A parameter with a default is a path that omits the organisation."""
        search = _methods()["search"]
        parameters = [argument.arg for argument in search.args.args]

        assert parameters[1] == "tenant"
        # Defaults bind to the tail of the parameter list. A tenant with a default would mean
        # every parameter from it onward has one, so an empty default list is the assertion.
        assert not search.args.defaults[: len(parameters) - 2]

    def test_no_method_accepts_a_caller_supplied_filter(self) -> None:
        """An OData filter parameter would be the obvious injection target — reachable from
        retrieved content or chat text — and the way a query gets widened by accident."""
        suspicious = {"filter", "odata_filter", "where", "query_filter", "scope", "search_filter"}
        offenders = [
            f"{name}({argument.arg})"
            for name, method in _methods().items()
            for argument in method.args.args + method.args.kwonlyargs
            if argument.arg in suspicious
        ]

        assert not offenders, (
            "a retrieval method accepts a caller-supplied filter: "
            f"{offenders}. The organisation filter is built from trusted context and is not "
            "composable with anything a caller provides."
        )

    def test_the_filter_is_built_from_the_tenant_context_alone(self) -> None:
        """One function, taking one argument. Nothing else contributes to the expression."""
        tenant = admitted_tenant()

        assert tenant_filter(tenant) == f"tenant_id eq '{tenant.tenant_id.value}'"

    def test_two_organisations_never_produce_the_same_filter(self) -> None:
        """The filter distinguishes organisations, which is the whole of its job."""
        assert tenant_filter(admitted_tenant()) != tenant_filter(admitted_tenant())
