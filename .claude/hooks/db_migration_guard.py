#!/usr/bin/env python3
"""H2 - migration-without-approval guard.

Purpose: a change to a migration-owned file cannot be silently treated as an ordinary application
change. This guard is **path-based and deterministic**. It does not infer schema semantics, does not
judge whether the change is safe, does not decide whether it was approved, and does not modify any
file. Satisfying it is not approval - it points at ``.claude/skills/db-change/SKILL.md``, where the
approval requirement actually lives.

Governed surface, read off the repository as it stands:

  ragcore/migrations/**                     the Alembic revisions, env.py and script template
  ragcore/alembic.ini                       the Alembic configuration
  ragcore/src/ragcore/persistence/**        models the migration suite asserts match the DDL
                                            (the paths migrations.yml already watches)

Usage:
  db_migration_guard.py                 PreToolUse hook; reads the event on stdin
  db_migration_guard.py --paths A B     report which of A, B are governed
  db_migration_guard.py --diff [ref]    report which changed files are governed
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guardlib import run  # noqa: E402

PREFIXES = (
    "ragcore/migrations/",
    "ragcore/src/ragcore/persistence/",
)

EXACT = (
    "ragcore/alembic.ini",
    "alembic.ini",
)

MESSAGE = """This is a database migration surface, so the DB change gate applies BEFORE this edit.

Required procedure - .claude/skills/db-change/SKILL.md, governed by .claude/rules/50-database.md:

  1. DETECT    identify the schema change before any application-code change
  2. STOP      stop application implementation
  3. DESCRIBE  tables, columns, constraints, indexes, views, revision + down_revision and single
               head, data impact, backfill, nullability transitions, compatibility, downgrade path,
               identity-bearing fields (identity-plane-final.md 12.2), DB permission changes,
               checkpoint persistence impact
  4. APPROVE   explicit human approval - it cannot be inferred, and this guard is not approval
  5. IMPLEMENT + VALIDATE the database first (uv run pytest -q -m integration, from ragcore/)
  6. CONTINUE  only then resume application implementation

Escalate to an ADR before implementing if the change touches identity-bearing immutability, the
database permission boundary, or graph checkpoint persistence (which also triggers
.claude/rules/30-langgraph.md; the DB ordering still wins).

If the human has already approved this specific change and the database is being implemented first,
say so and proceed."""


if __name__ == "__main__":
    raise SystemExit(
        run(name="H2 migration guard", prefixes=PREFIXES, exact=EXACT, message=MESSAGE)
    )
