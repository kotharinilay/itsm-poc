#!/usr/bin/env python3
"""Validation for the Phase 4 governance artifacts. Standalone: run it with any Python 3.10+.

    python3 .claude/hooks/test_guards.py

It is deliberately NOT a pytest module and lives outside every project test root, so it cannot be
collected by ragcore, integrations or the .NET suites and cannot alter their results. It asserts
only governance artifacts; it touches no application code, no schema and no graph behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
ROOT = HOOKS.parent.parent
sys.path.insert(0, str(HOOKS))

import db_migration_guard as h2  # noqa: E402
import langgraph_change_guard as h3  # noqa: E402
from _guardlib import governed  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(label)


def edit_event(path: str, tool: str = "Edit") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def bash_event(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def guard_hits(guard, event: dict) -> list[str]:
    return governed(event, guard.PREFIXES, guard.EXACT)


def run_hook(script: str, event: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
    )


BS = chr(92)
WIN_MIGRATION = BS.join(["ragcore", "migrations", "versions", "0026_synthetic_change.py"])
WIN_GRAPH = BS.join(["ragcore", "src", "ragcore", "graph", "nodes", "governance.py"])

# --- H2: the migration surface triggers -------------------------------------------------------
MIGRATION_PATHS = [
    "ragcore/migrations/versions/0026_synthetic_change.py",
    "ragcore/migrations/env.py",
    "ragcore/alembic.ini",
    "ragcore/src/ragcore/persistence/models.py",
    WIN_MIGRATION,
]
for _p in MIGRATION_PATHS:
    check("H2 triggers on " + _p, guard_hits(h2, edit_event(_p)) != [])

# --- H3: the LangGraph surface triggers -------------------------------------------------------
GRAPH_PATHS = [
    "ragcore/src/ragcore/graph/builder.py",
    "ragcore/src/ragcore/graph/state.py",
    "ragcore/src/ragcore/graph/nodes/execution.py",
    "ragcore/src/ragcore/graph/checkpointer.py",
    "ragcore/workers/resume_worker.py",
    WIN_GRAPH,
]
for _p in GRAPH_PATHS:
    check("H3 triggers on " + _p, guard_hits(h3, edit_event(_p)) != [])

# --- unrelated paths trigger neither guard ----------------------------------------------------
UNRELATED = [
    "dotnet/src/Modules/Synthia.Modules.Sessions/SessionModule.cs",
    "apps/web/src/app/app.component.ts",
    "apps/desktop/src/main.ts",
    "integrations/src/integrations/connectors/servicenow.py",
    "ragcore/src/ragcore/retrieval/hybrid.py",
    "ragcore/src/ragcore/api/routes.py",
    "ragcore/tests/unit/test_nothing.py",
    "ragcore/workers/outbox_dispatch.py",
    "docs/architecture/RagAgent-Architecture-final.md",
    "README.md",
    ".github/workflows/ragcore.yml",
    "ragcore/migrations/versions/__pycache__/0001_platform_schema.cpython-312.pyc",
]
for _p in UNRELATED:
    check("H2 silent on " + _p, guard_hits(h2, edit_event(_p)) == [])
    check("H3 silent on " + _p, guard_hits(h3, edit_event(_p)) == [])

# the two guards own disjoint surfaces
check("H2 silent on graph paths", all(guard_hits(h2, edit_event(p)) == [] for p in GRAPH_PATHS))
check(
    "H3 silent on migration paths",
    all(guard_hits(h3, edit_event(p)) == [] for p in MIGRATION_PATHS),
)


# --- shell writes are caught; shell reads and mentions are not --------------------------------
check(
    "H2 triggers on a redirection into a migration",
    guard_hits(h2, bash_event("cat > ragcore/migrations/versions/0026_x.py")) != [],
)
check(
    "H3 triggers on sed -i against the graph",
    guard_hits(h3, bash_event("sed -i s/a/b/ ragcore/src/ragcore/graph/builder.py")) != [],
)
check(
    "H3 triggers on cp into the graph",
    guard_hits(h3, bash_event("cp /tmp/x.py ragcore/src/ragcore/graph/state.py")) != [],
)
check(
    "H2 silent on reading a migration",
    guard_hits(h2, bash_event("cat ragcore/migrations/versions/0001_platform_schema.py")) == [],
)
check(
    "H3 silent on grepping the graph",
    guard_hits(h3, bash_event("grep -n add_node ragcore/src/ragcore/graph/builder.py")) == [],
)
check(
    "H3 silent when a graph path appears only in a heredoc body",
    guard_hits(
        h3,
        bash_event(
            "cat > .claude/hooks/notes.txt <<'EOF'\nragcore/src/ragcore/graph/builder.py\nEOF"
        ),
    )
    == [],
)
check(
    "H2 silent on ls of the migrations directory",
    guard_hits(h2, bash_event("ls ragcore/migrations/versions")) == [],
)

# --- the hook contract end to end: exit 2 blocks, exit 0 passes -------------------------------
blocked = run_hook("db_migration_guard.py", edit_event("ragcore/migrations/versions/0026_x.py"))
check("H2 exits 2 on a governed write", blocked.returncode == 2)
check("H2 names the db-change skill", ".claude/skills/db-change/SKILL.md" in blocked.stderr)
check("H2 writes nothing to stdout", blocked.stdout.strip() == "")

passed = run_hook("db_migration_guard.py", edit_event("apps/web/src/app/app.component.ts"))
check("H2 exits 0 on an unrelated write", passed.returncode == 0)

blocked3 = run_hook("langgraph_change_guard.py", edit_event("ragcore/src/ragcore/graph/state.py"))
check("H3 exits 2 on a governed write", blocked3.returncode == 2)
check(
    "H3 names the langgraph-change skill",
    ".claude/skills/langgraph-change/SKILL.md" in blocked3.stderr,
)
check("H3 requires an accepted ADR in its message", "ACCEPTED" in blocked3.stderr)

passed3 = run_hook("langgraph_change_guard.py", edit_event("dotnet/src/Api/Program.cs"))
check("H3 exits 0 on an unrelated write", passed3.returncode == 0)

malformed = subprocess.run(
    [sys.executable, str(HOOKS / "db_migration_guard.py")],
    input="not json",
    capture_output=True,
    text=True,
    check=False,
)
check("a guard that cannot read its input does not block", malformed.returncode == 0)


# --- governance artifacts exist and are well formed -------------------------------------------
RULES = [ROOT / ".claude/rules/30-langgraph.md", ROOT / ".claude/rules/50-database.md"]
SKILLS = [
    ROOT / ".claude/skills/db-change/SKILL.md",
    ROOT / ".claude/skills/langgraph-change/SKILL.md",
]

for _f in RULES + SKILLS:
    check("exists: " + _f.name + " (" + _f.parent.name + ")", _f.is_file())

for _f in RULES:
    text = _f.read_text(encoding="utf-8")
    check(_f.name + " has a single H1", text.count("\n# ") + text.startswith("# ") == 1)
    check(_f.name + " has balanced code fences", text.count("```") % 2 == 0)
    check(
        _f.name + " states the ordering", "DETECT" in text and "STOP" in text and "APPROVE" in text
    )
    check(_f.name + " forbids inferred approval", "infer" in text.lower())

for _f in SKILLS:
    text = _f.read_text(encoding="utf-8")
    check(_f.name + " opens with frontmatter", text.startswith("---\n"))
    body = text.split("---\n", 2)
    check(_f.parent.name + " frontmatter closes", len(body) == 3)
    front = body[1]
    check(
        _f.parent.name + " frontmatter names the skill", 'name: "' + _f.parent.name + '"' in front
    )
    check(_f.parent.name + " frontmatter has a description", "description:" in front)
    check(_f.parent.name + " has balanced code fences", body[2].count("```") % 2 == 0)
    check(
        _f.parent.name + " never self-approves",
        "never approve" in text.lower() or "must never do" in text.lower(),
    )

db_rule = (ROOT / ".claude/rules/50-database.md").read_text(encoding="utf-8")
for _needle in (
    "identity-bearing",
    "permission boundary",
    "checkpoint",
    "downgrade",
    "backfill",
    "nullability",
    "single head",
):
    check("50-database.md covers " + _needle, _needle in db_rule.lower())

graph_rule = (ROOT / ".claude/rules/30-langgraph.md").read_text(encoding="utf-8")
for _needle in (
    "execution_treatment",
    "interrupt",
    "resume",
    "termination",
    "side effect",
    "ADR",
    "tenant",
    "never owns execution authority",
    "checkpoint",
):
    check("30-langgraph.md covers " + _needle, _needle in graph_rule)

# --- Spec Kit machinery is intact -------------------------------------------------------------
speckit = sorted((ROOT / ".claude/skills").glob("speckit-*/SKILL.md"))
check("Spec Kit skills still present", len(speckit) == 10)

# --- the committed hook configuration is valid and wires both guards --------------------------
settings_path = ROOT / ".claude/settings.json"
check("settings.json exists", settings_path.is_file())
settings = json.loads(settings_path.read_text(encoding="utf-8"))
entries = settings.get("hooks", {}).get("PreToolUse", [])
commands = [h.get("command", "") for entry in entries for h in entry.get("hooks", [])]
check("H2 is wired", any("db_migration_guard.py" in c for c in commands))
check("H3 is wired", any("langgraph_change_guard.py" in c for c in commands))
check("hooks are PreToolUse", bool(entries))
check(
    "the matcher covers file-writing tools",
    all("Write" in e.get("matcher", "") and "Edit" in e.get("matcher", "") for e in entries),
)

print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
for failure in FAILURES:
    print("FAILED: " + failure)
raise SystemExit(1 if FAILURES else 0)
