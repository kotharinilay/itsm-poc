#!/usr/bin/env python3
"""Validation for the Phase 4 and Phase 5 governance artifacts. Standalone: any Python 3.10+.

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

import adr_structure_guard as h5  # noqa: E402
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


def outside_fences(text: str) -> str:
    """The document with fenced blocks removed. A markdown example inside a fence is an example,
    not a heading of the document that shows it."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


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


# --- H5: the ADR surface, and only the ADR surface --------------------------------------------
ADR_PATHS = [
    "docs/adr/0010-a-new-decision.md",
    "docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md",
    BS.join(["docs", "adr", "0010-a-new-decision.md"]),
]
for _p in ADR_PATHS:
    check("H5 governs " + _p, h5.is_governed(_p))

NOT_ADR = [
    "docs/adr/README.md",
    "docs/adr/readme.md",
    "docs/adr/templates/madr.md",
    "docs/architecture/RagAgent-Architecture-final.md",
    "docs/migration/phase-2-authority-model.md",
    "ragcore/migrations/versions/0026_x.py",
    "ragcore/src/ragcore/graph/builder.py",
    "README.md",
]
for _p in NOT_ADR:
    check("H5 silent on " + _p, not h5.is_governed(_p))

# the three guards own disjoint surfaces
check("H5 silent on migration paths", not any(h5.is_governed(p) for p in MIGRATION_PATHS))
check("H5 silent on graph paths", not any(h5.is_governed(p) for p in GRAPH_PATHS))
for _p in ADR_PATHS:
    check("H2 silent on " + _p, guard_hits(h2, edit_event(_p)) == [])
    check("H3 silent on " + _p, guard_hits(h3, edit_event(_p)) == [])

# --- H5: the next number is read off the existing history -------------------------------------
KNOWN = h5.existing_numbers()
check("H5 sees the nine historical records", sorted(KNOWN) == list(range(1, 10)))
check(
    "H5 excludes the index from the record set",
    all("readme" not in n.lower() for n in KNOWN.values()),
)
check("the next ADR number is 0010", max(KNOWN) + 1 == 10)

# --- H5: structural validation of a new record ------------------------------------------------
VALID_ADR = """# 0010. A deliberate decision about something

- **Status:** Proposed
- **Date:** 2026-09-20
- **Deciders:** Platform architecture owner

## Context and Problem Statement

A2 8.1 says one thing and the work needs another.

## Decision Outcome

The decision, stated so it cannot be read two ways.

## Consequences

What becomes true, and what it costs.
"""


def write_event(path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def h5_problems(path: str, content: str | None) -> list[str]:
    return h5.validate(path, content, is_new=True)


check(
    "a valid 0010 record passes",
    h5_problems("docs/adr/0010-a-deliberate-decision.md", VALID_ADR) == [],
)
check(
    "a duplicate number fails",
    any("already taken" in p for p in h5_problems("docs/adr/0005-duplicate.md", VALID_ADR)),
)
check(
    "a missing number fails",
    any(
        "four-digit" in p
        for p in h5_problems("docs/adr/a-decision-without-a-number.md", VALID_ADR)
    ),
)
check(
    "a non-sequential number fails",
    any(
        "does not continue the sequence" in p
        for p in h5_problems("docs/adr/0012-too-far-ahead.md", VALID_ADR)
    ),
)
check(
    "a malformed filename fails",
    any(
        "kebab-case" in p or "NNNN-" in p
        for p in h5_problems("docs/adr/0010-A_Title With Spaces.md", VALID_ADR)
    ),
)
check(
    "a missing Status fails",
    any(
        "Status" in p
        for p in h5_problems(
            "docs/adr/0010-no-status.md", VALID_ADR.replace("- **Status:** Proposed\n", "")
        )
    ),
)
check(
    "a missing Context fails",
    any(
        "Context" in p
        for p in h5_problems(
            "docs/adr/0010-no-context.md",
            VALID_ADR.replace("## Context and Problem Statement", "## Background"),
        )
    ),
)
check(
    "a missing Decision fails",
    any(
        "Decision" in p
        for p in h5_problems(
            "docs/adr/0010-no-decision.md", VALID_ADR.replace("## Decision Outcome", "## Outcome")
        )
    ),
)
check(
    "a missing Consequences fails",
    any(
        "Consequences" in p
        for p in h5_problems(
            "docs/adr/0010-no-consequences.md", VALID_ADR.replace("## Consequences", "## Notes")
        )
    ),
)
check(
    "a title heading that does not carry its own number fails",
    any(
        "does not carry" in p
        for p in h5_problems(
            "docs/adr/0010-wrong-title.md", VALID_ADR.replace("# 0010.", "# 0007.")
        )
    ),
)
check(
    "the minimal MADR dialect passes too",
    h5_problems(
        "docs/adr/0010-minimal-dialect.md",
        "# ADR-0010: A decision\n\n- Status: Proposed\n- Date: 2026-09-20\n\n"
        "## Context\n\nx\n\n## Decision\n\ny\n\n## Consequences\n\nz\n",
    )
    == [],
)

# --- H5: the hook contract end to end ---------------------------------------------------------
h5_ok = run_hook("adr_structure_guard.py", write_event("docs/adr/0010-a-good-record.md", VALID_ADR))
check("H5 exits 0 on a structurally valid new record", h5_ok.returncode == 0)
check("H5 says nothing when it passes", h5_ok.stdout.strip() == "" and h5_ok.stderr.strip() == "")

h5_bad = run_hook("adr_structure_guard.py", write_event("docs/adr/0005-duplicate.md", VALID_ADR))
check("H5 exits 2 on a structurally invalid record", h5_bad.returncode == 2)
check("H5 names the rule", "70-adr.md" in h5_bad.stderr)
check("H5 writes nothing to stdout", h5_bad.stdout.strip() == "")

h5_history = run_hook(
    "adr_structure_guard.py",
    edit_event("docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md"),
)
check("H5 flags a write to an existing historical record", h5_history.returncode == 2)
check("H5 says history is preserved", "historical records" in h5_history.stderr)

h5_unrelated = run_hook("adr_structure_guard.py", edit_event("docs/adr/README.md"))
check("H5 exits 0 on the ADR index", h5_unrelated.returncode == 0)
h5_elsewhere = run_hook("adr_structure_guard.py", edit_event("ragcore/src/ragcore/graph/state.py"))
check("H5 exits 0 on an unrelated write", h5_elsewhere.returncode == 0)

h5_malformed = subprocess.run(
    [sys.executable, str(HOOKS / "adr_structure_guard.py")],
    input="not json",
    capture_output=True,
    text=True,
    check=False,
)
check("H5 does not block when it cannot read its input", h5_malformed.returncode == 0)

# H5 decides structure, never acceptance, and never writes
h5_source = (HOOKS / "adr_structure_guard.py").read_text(encoding="utf-8")
check("H5 never writes a file", "write_text" not in h5_source and "open(" not in h5_source)
check("H5 never sets a status", "Accepted" not in h5_source.replace("'Accepted'", ""))
check("H5 points at the authoring skill's requirement", "acceptance" in h5_source.lower())

# --- H5 leaves the historical records exactly as they are -------------------------------------
HISTORY = sorted((ROOT / "docs/adr").glob("0*.md"))
check("the nine historical records are present", len(HISTORY) == 9)
BEFORE = {f.name: f.read_bytes() for f in HISTORY}
for _event in (
    write_event("docs/adr/0010-a-good-record.md", VALID_ADR),
    write_event("docs/adr/0005-duplicate.md", VALID_ADR),
    edit_event("docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md"),
):
    run_hook("adr_structure_guard.py", _event)
check(
    "H5 modified no historical record",
    all(f.read_bytes() == BEFORE[f.name] for f in HISTORY),
)
check(
    "H5 created no record of its own",
    not (ROOT / "docs/adr/0010-a-good-record.md").exists(),
)


# --- governance artifacts exist and are well formed -------------------------------------------
RULES = [ROOT / ".claude/rules/30-langgraph.md", ROOT / ".claude/rules/50-database.md"]
ADR_RULE = ROOT / ".claude/rules/70-adr.md"
SKILLS = [
    ROOT / ".claude/skills/db-change/SKILL.md",
    ROOT / ".claude/skills/langgraph-change/SKILL.md",
    ROOT / ".claude/skills/adr-author/SKILL.md",
]

for _f in RULES + [ADR_RULE] + SKILLS:
    check("exists: " + _f.name + " (" + _f.parent.name + ")", _f.is_file())

for _f in RULES + [ADR_RULE]:
    text = _f.read_text(encoding="utf-8")
    prose = outside_fences(text)
    check(_f.name + " has a single H1", prose.count("\n# ") + prose.startswith("# ") == 1)
    check(_f.name + " has balanced code fences", text.count("```") % 2 == 0)
    check(_f.name + " forbids inferred approval", "infer" in text.lower())

for _f in RULES:
    text = _f.read_text(encoding="utf-8")
    check(
        _f.name + " states the ordering", "DETECT" in text and "STOP" in text and "APPROVE" in text
    )

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

adr_rule = ADR_RULE.read_text(encoding="utf-8")
check("70-adr.md states the ordering", all(w in adr_rule for w in ("DETECT", "STOP", "ACCEPT")))
for _needle in (
    "architecture change",
    "engineering-baseline change",
    "identity-bearing immutability",
    "permission boundar",
    "checkpoint persistence",
    "30-langgraph.md",
    "50-database.md",
    "madr",
    "status",
    "proposed",
    "0010",
    "sequential",
    "historical record",
    "never",
):
    check("70-adr.md covers " + _needle, _needle in adr_rule.lower())
check(
    "70-adr.md keeps writing and accepting separate",
    "Writing an ADR is not approval of it." in adr_rule,
)
check(
    "70-adr.md does not duplicate the 30.4 trigger list",
    adr_rule.count("execution_treatment") <= 1,
)
check("70-adr.md names the three architecture documents", all(
    d in adr_rule
    for d in (
        "identity-plane-final.md",
        "Synthia-OverallArchitecture-final.md",
        "RagAgent-Architecture-final.md",
    )
))
check(
    "70-adr.md excludes the non-authoritative architecture files",
    "integrations-service-delta.md" in adr_rule and "ragcore-langgraph-flow.md" in adr_rule,
)

adr_skill = (ROOT / ".claude/skills/adr-author/SKILL.md").read_text(encoding="utf-8")
check("adr-author is procedural", adr_skill.count("## Step ") >= 9)
check("adr-author stops before implementation", "STOP" in adr_skill)
check("adr-author separates drafting from acceptance", "HUMAN ACCEPTANCE" in adr_skill.upper())
check("adr-author self-checks before stopping", "SELF-CHECK" in adr_skill.upper())
check("adr-author names the architecture owner", "owning document" in adr_skill)
check(
    "adr-author refuses to choose an architecture for a human",
    "when the choice is a human's" in adr_skill,
)
check("adr-author defers the trigger lists to the rules", "70-adr.md" in adr_skill)

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
check("H5 is wired", any("adr_structure_guard.py" in c for c in commands))
GUARDS = ("db_migration_guard.py", "langgraph_change_guard.py", "adr_structure_guard.py")
check(
    "each guard is wired exactly once",
    all(sum(guard in c for c in commands) == 1 for guard in GUARDS),
)
check("no developer-local hook override", "hooks" not in json.loads(
    (ROOT / ".claude/settings.local.json").read_text(encoding="utf-8")
) if (ROOT / ".claude/settings.local.json").is_file() else True)
check("hooks are PreToolUse", bool(entries))
check(
    "the matcher covers file-writing tools",
    all("Write" in e.get("matcher", "") and "Edit" in e.get("matcher", "") for e in entries),
)

print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
for failure in FAILURES:
    print("FAILED: " + failure)
raise SystemExit(1 if FAILURES else 0)
