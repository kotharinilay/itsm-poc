#!/usr/bin/env python3
"""H3 - LangGraph-change guard.

Purpose: a change to the graph implementation surface triggers the LangGraph governance procedure.
This guard is **path-based and deterministic**. It does not determine semantic correctness, does not
decide whether an ADR is required, does not modify application code and does not touch tests.
Satisfying it is not approval - it points at ``.claude/skills/langgraph-change/SKILL.md``.

Governed surface, read off the repository as it stands:

  ragcore/src/ragcore/graph/**          builder (topology), state (shape and reducers), nodes/,
                                        checkpointer, context, dependencies, host, threads,
                                        projections
  ragcore/workers/resume_worker.py      non-live resume servicing of a suspended run

Usage:
  langgraph_change_guard.py                 PreToolUse hook; reads the event on stdin
  langgraph_change_guard.py --paths A B     report which of A, B are governed
  langgraph_change_guard.py --diff [ref]    report which changed files are governed
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guardlib import run  # noqa: E402

PREFIXES = ("ragcore/src/ragcore/graph/",)

EXACT = ("ragcore/workers/resume_worker.py",)

MESSAGE = """This is the LangGraph implementation surface, so the workflow change gate applies
BEFORE this edit.

Required procedure - .claude/skills/langgraph-change/SKILL.md, governed by
.claude/rules/30-langgraph.md:

  1. DETECT    identify that the change alters nodes, edges, routing, topology, state shape or
               semantics, interrupts, resume, execution ordering, termination, clarify loop,
               retrieval or resolution routing, approval flow, execution treatment, checkpoint
               persistence, or side-effect boundaries
  2. STOP      stop implementation
  3. DESCRIBE  the affected nodes, edges, topology, state, interrupts, resume, routing, execution
               order, termination, checkpoint persistence, authority behavior and side effects
  4. CLASSIFY  workflow-only, or architecture/authority-changing (rule 30.4)
  5. APPROVE   explicit human approval - it cannot be inferred, and this guard is not approval
  6. ADR       if architecture/authority-changing: a MADR ADR in docs/adr/, ACCEPTED, before any
               implementation. Writing one is not accepting one.
  7. IMPLEMENT   8. TEST   9. VERIFY

The execution-authority protections in rule 30.3 are not weakened by any change: the LLM never owns
execution authority and cannot establish or replace tenant, requester, approval or execution
identity; no side effect occurs directly from an agent node; execution re-reads the authoritative
durable work item first; model output, retrieved content, chat text, trigger payloads and realtime
messages cannot widen authority.

If the change also alters checkpoint persistence, the database gate runs first and to completion
(.claude/rules/50-database.md 50.6).

If the human has already approved this specific change - and accepted the ADR where one was
required - say so and proceed."""


if __name__ == "__main__":
    raise SystemExit(
        run(name="H3 LangGraph guard", prefixes=PREFIXES, exact=EXACT, message=MESSAGE)
    )
