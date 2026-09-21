"""SQLAlchemy models, repositories, unit of work. Every query applies tenant_id.

**PostgreSQL is the authoritative durable store for platform state** (A1 §4.5, A2 P03).
Three things are *not* here, and each has an owner elsewhere:

* **The case** belongs to ServiceNow, which remains its system of record. This schema holds a
  ``case_reference``, never a copy.
* **The retrieval index** is derived. A lost index is rebuilt by re-running ingestion, not restored.
* **Graph checkpoints** belong to the ``langgraph`` schema and the checkpointer's own ``setup()``.
  **No second durable checkpoint store exists** — see :mod:`ragcore.graph.checkpointer`.

The modules, in dependency order:

``base``
    The declarative base, the schema, and the audit / version / soft-delete conventions.
``enums``
    PostgreSQL enum types, each built from the domain enum it stores.
``models``
    Every table.
``views``
    The eleven published ``vw_*_v1`` views — the read contract with the .NET monolith.
``engine``
    The async engine and the unit of work the transactional outbox depends on.
``concurrency``
    Optimistic concurrency. No distributed lock, no Serializable transaction, no soft delete.
``repositories``
    Every query, each applying ``tenant_id``.
``retention``
    Windows, and the rule that the clock starts at the terminal state.
``erasure``
    Hard deletion of one organisation's data.
"""
