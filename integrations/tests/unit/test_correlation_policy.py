"""This service applies the platform's correlation rule on BOTH of its boundaries.

``build/policy/correlation-id.json`` is the rule; each deployable implements it and asserts it. This
service used to accept hex only — on the HTTP hop and on the command queue — so an identifier the
other deployables accepted was replaced here, and a command carrying one was dead-lettered: work a
governance decision had authorized never ran, for want of a log index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

import pytest

from integrations.api.middleware.correlation import _WELL_FORMED
from integrations.messaging.envelope import EnvelopeError, MessageEnvelope

POLICY_PATH: Final = (
    Path(__file__).resolve().parents[3] / "build" / "policy" / "correlation-id.json"
)
POLICY: Final[dict[str, Any]] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _command(correlation_id: str) -> str:
    return json.dumps(
        {"jobId": str(uuid4()), "correlationId": correlation_id, "kind": "integration.execute"}
    )


def test_the_pattern_is_the_policys() -> None:
    assert _WELL_FORMED.pattern == POLICY["pattern"]


class TestTheHttpBoundary:
    @pytest.mark.parametrize("candidate", POLICY["accept"])
    def test_a_well_formed_identifier_is_kept(self, candidate: str) -> None:
        assert _WELL_FORMED.fullmatch(candidate)

    @pytest.mark.parametrize("candidate", POLICY["reject"])
    def test_a_malformed_identifier_is_replaced(self, candidate: str) -> None:
        assert not _WELL_FORMED.fullmatch(candidate)


class TestTheCommandQueue:
    @pytest.mark.parametrize("candidate", POLICY["accept"])
    def test_a_command_carrying_a_platform_identifier_is_accepted(self, candidate: str) -> None:
        """The regression: ``req_abc.123`` was legal everywhere else and dead-lettered here."""
        assert MessageEnvelope.from_json(_command(candidate)).correlation_id == candidate

    @pytest.mark.parametrize("candidate", POLICY["reject"])
    def test_a_command_carrying_a_malformed_identifier_is_refused(self, candidate: str) -> None:
        with pytest.raises(EnvelopeError):
            MessageEnvelope.from_json(_command(candidate))

    def test_the_length_limit_is_inclusive(self) -> None:
        limit = POLICY["maxLength"]
        assert MessageEnvelope.from_json(_command("a" * limit)).correlation_id == "a" * limit
        with pytest.raises(EnvelopeError):
            MessageEnvelope.from_json(_command("a" * (limit + 1)))
