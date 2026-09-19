"""The checkpoint thread key. **One derivation, used by every reader and writer of a thread.**

A LangGraph thread holds a conversation's durable state — every turn, every suspension, and the
authority context of whatever work item the run is suspended on. Whoever can name a thread can
resume it. So the key is **derived from trusted identity plus the session**, never taken from a
request:

* **The organisation** comes from the admitted tenant binding, which the Gateway-derived identity
  and the registry produced. A caller from another organisation who learns a session identifier
  names a different thread, and finds it empty.
* **The requester** comes from the validated principal. Two users of one organisation who share a
  session identifier likewise name different threads.
* **The session** is what the client names — and is, on its own, not enough. It is the only part a
  caller supplies, which is exactly why it cannot be the whole key.

This matters most *before* the triage gate, when by design no ``chat_session`` row exists yet
(spec FR-SESS-003): there is no durable record to check ownership against, and the key is the only
thing standing between a session identifier and another user's conversation.

**The retention sweeper derives the same key** from the work item's immutable ``tenant_id``,
``requested_by_oid`` and ``session_id``. When the host keyed threads by session and the sweeper
pruned them by work item, the two never met: no conversation's checkpoints were ever removed.
"""

from __future__ import annotations

from uuid import UUID

__all__ = ["checkpoint_thread_id"]


def checkpoint_thread_id(tenant_id: UUID, requester_oid: UUID, session_id: UUID) -> str:
    """The thread a session's checkpoints live under.

    Args:
        tenant_id: The organisation, from the admitted tenant binding.
        requester_oid: The end user who owns the session, from the validated principal.
        session_id: The session the client named.

    Returns:
        A stable key. The same three inputs always give the same key, and changing any one of them
        gives a different one.
    """
    return f"{tenant_id}:{requester_oid}:{session_id}"
