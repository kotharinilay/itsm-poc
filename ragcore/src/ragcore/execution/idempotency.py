"""Idempotency boundary 2 — the key that makes an **external** effect happen at most once.

Boundary 1, the atomic claim, stops a second execution *attempt*. This stops a second *effect*, and
the difference is the case that makes both necessary: an attempt that reached the far side, changed
something there, and then failed before recording it. The claim cannot help — it was taken and the
work is now unclaimed again or escalated — but the key can, because the external system recognises
it and replays its original answer instead of acting twice.

**The key is derived, never random.** A random key is a new key on every attempt, which is precisely
the one thing an idempotency key must not be: the far side would see a fresh request and act again.
It is derived from the work item and the operation so that the *same* logical action produces the
*same* key however many times it is retried, from whichever replica.

**It carries no authority and no secret.** It is a correlating token, not a capability: possessing
one permits nothing. It is a hash rather than the raw identifiers concatenated so it is bounded in
length and carries no readable tenant or principal to a vendor's logs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from ragcore.application.ports import IdempotencyStorePort
from ragcore.domain.identifiers import IdempotencyKey, OperationId, WorkItemId
from ragcore.domain.tenancy import TenantContext

KEY_PREFIX: Final = "synthia-v1"
"""Versioned, so the derivation can change without colliding with keys already issued.

Without it, a change to what goes into the hash would silently produce a different key for work
already in flight — the external system would see a new request and act a second time, which is the
exact failure this module exists to prevent.
"""


def derive_key(
    tenant: TenantContext, work_item_id: WorkItemId, operation_id: OperationId
) -> IdempotencyKey:
    """Derive the idempotency key for one operation on one work item.

    Deterministic across processes, replicas and retries: the same three inputs always produce the
    same key, which is what lets a far side recognise a repeat.

    The tenant is included so two organisations cannot collide on one key even if identifiers were
    ever reused — and it is *hashed in* rather than emitted, so the key discloses no organisation to
    whoever receives it.

    Args:
        tenant: The organisation, from trusted context.
        work_item_id: The durable authority record.
        operation_id: The specific operation within it.

    Returns:
        The key.
    """
    material = f"{tenant.tenant_id}:{work_item_id}:{operation_id}".encode()
    digest = hashlib.sha256(material).hexdigest()
    return IdempotencyKey(f"{KEY_PREFIX}:{digest}")


@dataclass(frozen=True, slots=True)
class ReplayDecision:
    """Whether to act, or to return what a previous attempt already achieved."""

    key: IdempotencyKey
    replayed: bool
    outcome: Any = None

    @property
    def should_execute(self) -> bool:
        """Whether the caller should perform the effect.

        ``False`` means a previous attempt already did, and :attr:`outcome` is what it produced.
        """
        return not self.replayed


async def begin_effect(
    store: IdempotencyStorePort,
    tenant: TenantContext,
    key: IdempotencyKey,
) -> ReplayDecision:
    """Decide whether this attempt performs the effect or replays an earlier one.

    **Checked before acting, recorded after** — see :func:`complete_effect`. The gap between the two
    is real and is not closable from this side: an attempt can act and then die before recording,
    and the next attempt will act again. That is why the key is also sent *to* the external system,
    which is the only party able to deduplicate a request it has already applied. This store makes
    the common case cheap and correct; the far side makes the crash case correct.

    Args:
        store: The idempotency store.
        tenant: The organisation.
        key: The derived key.

    Returns:
        The decision.
    """
    previous = await store.replay(tenant, key)

    if previous is not None:
        return ReplayDecision(key=key, replayed=True, outcome=previous)

    return ReplayDecision(key=key, replayed=False)


async def complete_effect(
    store: IdempotencyStorePort,
    tenant: TenantContext,
    key: IdempotencyKey,
    operation_id: OperationId,
    outcome: dict[str, Any],
) -> None:
    """Record what the effect produced, so a repeat replays it.

    Args:
        store: The idempotency store.
        tenant: The organisation.
        key: The derived key.
        operation_id: The operation whose reserved row this completes.
        outcome: What to return to a later attempt. Must be serialisable and must carry no
            credential or authority — it is read back and returned to whoever repeats the request.
    """
    await store.remember(tenant, key, operation_id, outcome)
