"""The derived idempotency key. **Boundary 2, and it is derived, never random.**

Specification §29.4. Two boundaries, both required, and since ADR-0007 they live in different
deployables:

```text
Boundary 1 — platform:  the atomic claim on the work item.   Owner: RagCore.
Boundary 2 — external:  this key, carried to the far side.   Owner: the Integrations Service.
```

**Why derived rather than random.** A random key makes every attempt look like a new logical action,
so a redelivered command produces a second external effect and the boundary protects nothing. The
same three inputs must always produce the same key — that is what lets a far side, and the
`unique(idempotency_key)` constraint on the execution record, recognise a repeat as a repeat.

**The organisation is hashed in, not emitted.** Two organisations cannot collide on one key even if
identifiers were ever reused, and the key itself discloses no organisation to whoever receives it —
including a third-party system's logs, which are outside the platform's control.

**Derived AFTER the organisation is recovered from durable state, never from the message.** A key
derived from a message-supplied organisation would be a key an attacker could steer, which would let
one organisation's retry collide with another's first attempt.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

__all__ = ["KEY_LENGTH", "derive_key"]

# Namespaced so a key derived here cannot collide with one derived by any other platform component
# that happens to hash the same identifiers.
_NAMESPACE: Final = "synthia.integration.execution.v1"

KEY_LENGTH: Final = 64
"""The rendered length. SHA-256 hex, and the column is sized for it with room to spare."""


def derive_key(tenant_id: UUID, work_item_id: UUID, operation_id: UUID) -> str:
    """Derive the idempotency key for one operation on one work item.

    Deterministic across processes, replicas and retries: the same three inputs always produce the
    same key, which is what lets a far side recognise a repeat.

    Args:
        tenant_id: The organisation, **recovered from the durable job record**. Hashed in rather
            than emitted, so the key discloses no organisation to a third-party system's logs.
        work_item_id: The authority record this execution is spending.
        operation_id: The operation within it. Present because one work item may carry more than
            one operation, and a key without it would make two different actions look like retries
            of each other — which the unique constraint would then silently suppress.

    Returns:
        The key, as lowercase hex.
    """
    material = "\x1f".join((_NAMESPACE, str(tenant_id), str(work_item_id), str(operation_id)))
    # The unit separator, not a hyphen: UUIDs contain hyphens, so a hyphen-joined string could in
    # principle be produced by two different input triples. An ambiguous encoding is how two
    # distinct actions come to share a key.
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
