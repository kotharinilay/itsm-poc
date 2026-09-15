# Migrations

**RagCore owns every migration** — every table, and every published `vw_*_v1` view
(ADR-0001, ADR-0003). Alembic is the only tool that changes this schema.

The .NET monolith owns no schema. `Database.Migrate()`, `EnsureCreated()` and EF Core
migration files are prohibited there, and an architecture test enforces their absence.

Migrations run as a **gated job before revision activation, never at application startup** —
Container Apps runs multiple replicas and scales to zero, so anything at startup runs
concurrently, repeatedly, and at unpredictable times.

The `langgraph` schema is owned by the checkpointer's own `setup()` and is excluded from
Alembic autogenerate. There is no second durable checkpoint store.

Initialised at Stage 7 (T082). Empty until then, deliberately.
