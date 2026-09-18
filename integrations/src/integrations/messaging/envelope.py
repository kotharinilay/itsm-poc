"""The command and result envelopes. **Three fields, and nothing authority-bearing.**

Specification §27.2, `contracts/triggers.md`, `FR-INTEG-014`.

```json
{ "jobId": "…", "correlationId": "…", "kind": "integration.execute" }
```

**That is the entire payload.** Explicitly forbidden, and refused rather than ignored: tenant,
requester, roles, action, target, parameters, treatment, approval state, expiry, command content,
credentials, or any other authority-bearing value.

**Why the type refuses extra fields rather than dropping them.** Dropping would let a publisher
believe a field had been honoured, and would let a forged field sit in the queue looking accepted.
Refusing turns the attempt into a dead-lettered message with an alert — the one event worth seeing
(`FR-DEMO-025`).

**The job identifier is not an exception to the rule; it is the mechanism that makes the rule
affordable.** It is an opaque platform identifier of the same class as a work identifier: it names a
durable row, carries no organisation, actor, capability or authority, and grants nothing on its own.
The consumer reads its instruction from the row that identifier names, never from the message that
carried it — so an at-least-once redelivery, or a malformed publish, cannot become an ungoverned
external call.

```text
The message causes work to happen.
The durable job record provides the instruction, the authority and the tenant context.
```
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final
from uuid import UUID

__all__ = ["EnvelopeError", "MessageEnvelope", "MessageKind"]

# The closed field set. A message carrying anything else is refused.
_PERMITTED_FIELDS: Final = frozenset({"jobId", "correlationId", "kind"})

# Matches the correlation middleware's acceptance rule, so an identifier that was legal on the HTTP
# hop is still legal on the queue. Two different rules would make one journey's identifier valid at
# one boundary and rejected at the next.
_WELL_FORMED_CORRELATION: Final = re.compile(r"^[0-9a-fA-F-]{8,128}$")


class MessageKind(Enum):
    """The closed kind set for the integration seam.

    `kind` is a **routing hint only**. The consumer reads authority from the durable record either
    way, and a consumer that decided anything from `kind` would be defective — which is why there is
    no branch on it that reaches an external system.
    """

    EXECUTE = "integration.execute"
    """RagCore has an authorized capability to run. Consumed by the Integrations Service."""

    COMPLETED = "integration.completed"
    """An execution finished and its outcome is durable. Consumed by RagCore."""

    FAILED = "integration.failed"
    """An execution did not complete. Consumed by RagCore, **never as a re-dispatch**."""


class EnvelopeError(Exception):
    """A message did not satisfy the envelope contract.

    **Carries no fragment of the offending message.** This exception is the thing most likely to be
    logged, and a message that violated the contract is exactly the content not to put in a log
    line — a forged field could carry an organisation identifier or a log-format token.
    """


@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """One message on the integration seam.

    Attributes:
        job_id: The opaque durable-row identifier. Grants nothing on its own.
        correlation_id: The journey, carried unchanged across the gateway hop and both queues.
        kind: The routing hint.
    """

    job_id: UUID
    correlation_id: str
    kind: MessageKind

    def to_json(self) -> str:
        """Serialise to the wire form.

        Returns:
            A compact JSON document carrying exactly three fields. Keys sorted so two publications
            of the same envelope are byte-identical, which is what lets a queue inspection be
            diffed rather than eyeballed.
        """
        return json.dumps(
            {
                "jobId": str(self.job_id),
                "correlationId": self.correlation_id,
                "kind": self.kind.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> MessageEnvelope:
        """Parse and validate a received message.

        Args:
            raw: The message body.

        Returns:
            The envelope.

        Raises:
            EnvelopeError: When the body is not a JSON object, carries a field the contract does not
                name, omits one it does, or carries a malformed value. **Every one of these is a
                refusal, and the caller dead-letters rather than repairing.** A message that does
                not match its contract has either come from a publisher nobody updated or from
                somewhere it should not have, and both want a human to look.
        """
        try:
            decoded: Any = json.loads(raw)
        except ValueError as error:
            raise EnvelopeError("the message body is not valid JSON") from error

        if not isinstance(decoded, dict):
            raise EnvelopeError("the message body is not a JSON object")

        present = set(decoded)

        # THE CHECK THAT MATTERS. A `tenantId`, `roles`, `parameters` or `treatment` field lands
        # here and is refused — not stripped, because stripping returns success to whoever sent it
        # and leaves the attempt indistinguishable from an ordinary message.
        forbidden = present - _PERMITTED_FIELDS
        if forbidden:
            raise EnvelopeError(
                f"the message carries {len(forbidden)} field(s) the envelope contract does not "
                "permit. A trigger carries an opaque identifier, correlation context and a routing "
                "kind; authority comes from the durable record."
            )

        missing = _PERMITTED_FIELDS - present
        if missing:
            raise EnvelopeError(f"the message omits {len(missing)} required field(s)")

        return cls(
            job_id=cls._job_id(decoded["jobId"]),
            correlation_id=cls._correlation_id(decoded["correlationId"]),
            kind=cls._kind(decoded["kind"]),
        )

    @staticmethod
    def _job_id(value: object) -> UUID:
        try:
            return UUID(str(value))
        except (ValueError, AttributeError) as error:
            raise EnvelopeError("the job identifier is not a UUID") from error

    @staticmethod
    def _correlation_id(value: object) -> str:
        candidate = str(value)
        if not _WELL_FORMED_CORRELATION.match(candidate):
            # Not merely tidiness: a correlation identifier is an index into telemetry, and one a
            # publisher can shape freely is an injection point into every log line carrying it.
            raise EnvelopeError("the correlation identifier is malformed")
        return candidate

    @staticmethod
    def _kind(value: object) -> MessageKind:
        try:
            return MessageKind(str(value))
        except ValueError as error:
            # A KIND OUTSIDE THE CLOSED SET IS NEVER TREATED AS AUTHORIZATION TO PROCEED. It
            # dead-letters, which is the correct behaviour under the trigger contract rather than a
            # gap in it.
            raise EnvelopeError("the message kind is outside the closed set") from error
