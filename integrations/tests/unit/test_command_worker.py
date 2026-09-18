"""The command worker's entry point: settlement mapping and the dead-letter signal.

**`integrations/workers/command_consumer.py` did not exist before this**, although the task naming
it was marked complete. The handling policy lived in `messaging/consumer.py` with nothing to run it.

What these pin is the part a test can pin without a namespace: that every disposition has exactly
one settlement call, and that a dead-letter is logged loudly and without disclosing the message.
**Getting the settlement mapping wrong is how a dead-letter silently becomes a completion** — which
makes approved-but-not-executed work disappear instead of surfacing.
"""

from __future__ import annotations

import logging

import pytest
from workers.command_consumer import SETTLEMENT, handle_command, main

from integrations.messaging.consumer import Disposition, HandledMessage

pytestmark = pytest.mark.governance


class _Consumer:
    """A consumer returning a fixed verdict, recording what it was handed."""

    def __init__(self, verdict: HandledMessage) -> None:
        self._verdict = verdict
        self.bodies: list[str] = []

    async def handle(self, body: str) -> HandledMessage:
        self.bodies.append(body)
        return self._verdict


def test_every_disposition_has_exactly_one_settlement_call() -> None:
    """A disposition with no settlement is a message received, acted on, and left to reappear.

    At lock expiry it is redelivered — so a missing entry does not fail loudly, it silently turns
    at-most-once handling into a loop. Derived from the enum rather than listed, so adding a
    disposition fails here rather than falling through.
    """
    assert set(SETTLEMENT) == set(Disposition)
    assert len(set(SETTLEMENT.values())) == len(Disposition)


def test_the_settlement_names_are_the_service_bus_receiver_methods() -> None:
    """Pinned as literals because they are an SDK contract, not a naming choice.

    A typo here is discovered only at runtime against a real namespace — which is the one place
    this scaffold cannot test.
    """
    assert SETTLEMENT[Disposition.COMPLETE] == "complete_message"
    assert SETTLEMENT[Disposition.DEAD_LETTER] == "dead_letter_message"
    assert SETTLEMENT[Disposition.ABANDON] == "abandon_message"


async def test_the_verdict_is_returned_unchanged_and_the_body_reaches_the_consumer() -> None:
    """The worker adds logging and a named seam; it does not second-guess the disposition."""
    consumer = _Consumer(HandledMessage(disposition=Disposition.COMPLETE))

    handled = await handle_command(consumer, '{"jobId":"x"}')  # type: ignore[arg-type]

    assert handled.disposition is Disposition.COMPLETE
    assert consumer.bodies == ['{"jobId":"x"}']


async def test_a_dead_letter_is_logged_at_warning_and_says_it_will_not_be_replayed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`FR-DEMO-025`: the one event worth seeing.

    Warning rather than info because a dead-lettered command may mean **authorized work never
    ran** — a governance failure, not an operational one.
    """
    consumer = _Consumer(
        HandledMessage(disposition=Disposition.DEAD_LETTER, reason="out-of-contract field")
    )

    with caplog.at_level(logging.WARNING, logger="workers.command_consumer"):
        await handle_command(consumer, "{}")  # type: ignore[arg-type]

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "will not be replayed" in caplog.records[0].getMessage()


async def test_the_dead_letter_log_carries_no_fragment_of_the_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A message that violated its contract is exactly the content not to copy into a log line.

    The reason names the *class* of problem. The body — which may carry a forged organisation
    identifier or a log-format token — never appears.
    """
    forged = '{"jobId":"x","tenantId":"acme-corporation"}'
    consumer = _Consumer(
        HandledMessage(disposition=Disposition.DEAD_LETTER, reason="out-of-contract field")
    )

    with caplog.at_level(logging.WARNING, logger="workers.command_consumer"):
        await handle_command(consumer, forged)  # type: ignore[arg-type]

    logged = caplog.records[0].getMessage()
    assert "acme-corporation" not in logged
    assert "tenantId" not in logged


@pytest.mark.parametrize(
    "disposition", [Disposition.COMPLETE, Disposition.ABANDON], ids=["complete", "abandon"]
)
async def test_a_non_dead_letter_disposition_logs_nothing(
    disposition: Disposition, caplog: pytest.LogCaptureFixture
) -> None:
    """Only the alertable event is logged.

    A warning per completed message would make the dead-letter line the one nobody notices, which
    is the same failure as not logging it at all.
    """
    consumer = _Consumer(HandledMessage(disposition=disposition))

    with caplog.at_level(logging.WARNING, logger="workers.command_consumer"):
        await handle_command(consumer, "{}")  # type: ignore[arg-type]

    assert caplog.records == []


def test_the_worker_refuses_to_start_rather_than_listening_to_nothing() -> None:
    """Deliberately loud, matching RagCore's five workers.

    A worker that started, logged "listening" and consumed no message would look healthy while
    approved work accumulated unexecuted — the failure this platform is least able to detect.
    """
    with pytest.raises(NotImplementedError, match="process wiring"):
        main()
