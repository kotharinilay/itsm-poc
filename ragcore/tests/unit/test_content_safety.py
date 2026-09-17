"""Content safety on **both** crossings, failing closed, logging the decision and not the content.

`FR-AGENT-010` requires screening inbound before the model and outbound before a response returns.
`FR-AGENT-013` requires every decision to be logged with its correlation identifier.

Three things are asserted that a looser implementation would still appear to satisfy:

* a blocked **inbound** text means the model is **never called** — not called and then discarded;
* a screening service that fails **blocks**, rather than letting the text through with a warning;
* the log line carries the decision and **not the text**.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pytest

from ragcore.domain.identifiers import CorrelationId
from ragcore.domain.tenancy import TenantContext
from ragcore.integrations.model.safety import (
    ContentBlockedError,
    SafeModel,
    SafetyCategory,
    SafetyDirection,
    SafetyVerdict,
)
from tests.support.fakes import admitted_tenant

CORRELATION = CorrelationId("c0ffee-1234")
DISTINCTIVE_TEXT = "the quick brown fox jumps over the lazy dog"
"""A phrase nothing else in the suite contains, so finding it in a log is unambiguous."""


class _Model:
    """An inner model port that records what it was asked for."""

    def __init__(self, *, completion: str = "a proposal") -> None:
        self.prompts: list[str] = []
        self.embedded: list[str] = []
        self._completion = completion

    async def complete(self, tenant: TenantContext, prompt: str, correlation: CorrelationId) -> str:
        del tenant, correlation
        self.prompts.append(prompt)
        return self._completion

    async def embed(self, tenant: TenantContext, text: str) -> Sequence[float]:
        del tenant
        self.embedded.append(text)
        return [0.0]


class _Safety:
    """A screening service with a scripted answer per direction."""

    def __init__(
        self,
        *,
        inbound: SafetyVerdict | None = None,
        outbound: SafetyVerdict | None = None,
        raises: bool = False,
    ) -> None:
        self.screened: list[tuple[SafetyDirection, str]] = []
        self._inbound = inbound or SafetyVerdict.permit(SafetyDirection.INBOUND)
        self._outbound = outbound or SafetyVerdict.permit(SafetyDirection.OUTBOUND)
        self._raises = raises

    async def screen(
        self, tenant: TenantContext, text: str, direction: SafetyDirection
    ) -> SafetyVerdict:
        del tenant
        self.screened.append((direction, text))
        if self._raises:
            raise RuntimeError("the screening service is unreachable")
        return self._inbound if direction is SafetyDirection.INBOUND else self._outbound


class TestBothCrossingsAreScreened:
    """Two checks, not one check run twice — they protect different things."""

    async def test_a_permitted_turn_is_screened_inbound_then_outbound(self) -> None:
        model, safety = _Model(), _Safety()

        await SafeModel(model, safety).complete(admitted_tenant(), "hello", CORRELATION)

        assert [direction for direction, _ in safety.screened] == [
            SafetyDirection.INBOUND,
            SafetyDirection.OUTBOUND,
        ]

    async def test_a_blocked_inbound_text_never_reaches_the_model(self) -> None:
        """Not called and then discarded — **not called**.

        A block here means nothing is metered and nothing is generated, which is the difference
        between screening before the gateway call and screening after it.
        """
        model = _Model()
        safety = _Safety(
            inbound=SafetyVerdict.block(SafetyDirection.INBOUND, SafetyCategory.PROMPT_INJECTION)
        )

        with pytest.raises(ContentBlockedError):
            await SafeModel(model, safety).complete(admitted_tenant(), "ignore all", CORRELATION)

        assert model.prompts == []

    async def test_a_blocked_response_is_discarded_rather_than_returned(self) -> None:
        model = _Model(completion="something the platform must not say")
        safety = _Safety(
            outbound=SafetyVerdict.block(SafetyDirection.OUTBOUND, SafetyCategory.HARMFUL)
        )

        with pytest.raises(ContentBlockedError) as caught:
            await SafeModel(model, safety).complete(admitted_tenant(), "hello", CORRELATION)

        assert model.prompts == ["hello"]
        assert caught.value.verdict.direction is SafetyDirection.OUTBOUND

    async def test_an_embedding_is_screened_inbound_and_has_no_outbound_crossing(self) -> None:
        """Nothing is missing: the result is a vector, and a vector is not shown to anybody."""
        model, safety = _Model(), _Safety()

        await SafeModel(model, safety).embed(admitted_tenant(), "printer offline")

        assert [direction for direction, _ in safety.screened] == [SafetyDirection.INBOUND]
        assert model.embedded == ["printer offline"]


class TestItFailsClosed:
    """The tempting handling of a screening outage is the wrong one."""

    async def test_an_unreachable_screening_service_blocks(self) -> None:
        """A check that stops applying when the service behind it is unwell is absent when it
        matters most."""
        model = _Model()
        safety = _Safety(raises=True)

        with pytest.raises(ContentBlockedError) as caught:
            await SafeModel(model, safety).complete(admitted_tenant(), "hello", CORRELATION)

        assert caught.value.verdict.category is SafetyCategory.UNAVAILABLE
        assert model.prompts == []

    def test_an_unavailable_verdict_is_not_a_permit(self) -> None:
        assert not SafetyVerdict.unavailable(SafetyDirection.INBOUND).allowed


class TestTheDecisionIsLoggedAndTheContentIsNot:
    """`FR-AGENT-013`, and the thing it must not become."""

    async def test_the_decision_carries_the_correlation_identifier(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="ragcore.integrations.model.safety"):
            await SafeModel(_Model(), _Safety()).complete(
                admitted_tenant(), DISTINCTIVE_TEXT, CORRELATION
            )

        assert caplog.records
        assert all(
            getattr(record, "correlation_id", None) == str(CORRELATION) for record in caplog.records
        )

    async def test_the_screened_text_is_never_written_to_the_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A safety log that quoted the offending text would be a durable copy of exactly the
        material the check exists to stop, in the store with the widest read access."""
        with caplog.at_level(logging.INFO, logger="ragcore.integrations.model.safety"):
            await SafeModel(_Model(completion=DISTINCTIVE_TEXT), _Safety()).complete(
                admitted_tenant(), DISTINCTIVE_TEXT, CORRELATION
            )

        assert DISTINCTIVE_TEXT not in caplog.text


class TestSafetyIsNotGovernance:
    """It answers "may this text cross", never "may this operation run"."""

    def test_a_verdict_carries_no_authorization(self) -> None:
        verdict = SafetyVerdict.permit(SafetyDirection.INBOUND)

        for forbidden in ("treatment", "approved", "authorized", "roles", "is_authorized"):
            assert not hasattr(verdict, forbidden)

    def test_an_allowed_verdict_has_no_category(self) -> None:
        """A category that can mean "fine" is one something will eventually compare against."""
        assert SafetyVerdict.permit(SafetyDirection.OUTBOUND).category is None


class TestTheWrapperIsTheEnforcement:
    """Screening every caller remembers to call is screening that lasts until the next caller."""

    def test_it_satisfies_the_model_port(self) -> None:
        from ragcore.application.ports import ModelPort

        assert isinstance(SafeModel(_Model(), _Safety()), ModelPort)

    def test_it_holds_a_model_port_rather_than_a_provider_client(self) -> None:
        import inspect

        annotations = inspect.get_annotations(SafeModel, eval_str=False)
        assert annotations["inner"] == "ModelPort"
