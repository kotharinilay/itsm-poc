#!/usr/bin/env python3
"""Validation for the Phase 4 and Phase 5 governance artifacts. Standalone: any Python 3.10+.

    python3 .claude/hooks/test_guards.py

It is deliberately NOT a pytest module and lives outside every project test root, so it cannot be
collected by ragcore, integrations or the .NET suites and cannot alter their results. It asserts
only governance artifacts; it touches no application code, no schema and no graph behavior.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
ROOT = HOOKS.parent.parent
sys.path.insert(0, str(HOOKS))

import adr_structure_guard as h5  # noqa: E402
import db_migration_guard as h2  # noqa: E402
import langgraph_change_guard as h3  # noqa: E402
from _guardlib import governed, reset_root_cache  # noqa: E402

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
    "docs/adr/0013-a-new-decision.md",
    "docs/adr/0001-ragcore-owns-orchestration-dotnet-owns-read.md",
    BS.join(["docs", "adr", "0013-a-new-decision.md"]),
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
check("H5 sees the twelve historical records", sorted(KNOWN) == list(range(1, 13)))
check(
    "H5 excludes the index from the record set",
    all("readme" not in n.lower() for n in KNOWN.values()),
)
check("the next ADR number is 0013", max(KNOWN) + 1 == 13)

# --- H5: structural validation of a new record ------------------------------------------------
VALID_ADR = """# 0013. A deliberate decision about something

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
    "a valid 0013 record passes",
    h5_problems("docs/adr/0013-a-deliberate-decision.md", VALID_ADR) == [],
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
        for p in h5_problems("docs/adr/0014-too-far-ahead.md", VALID_ADR)
    ),
)
check(
    "a malformed filename fails",
    any(
        "kebab-case" in p or "NNNN-" in p
        for p in h5_problems("docs/adr/0013-A_Title With Spaces.md", VALID_ADR)
    ),
)
check(
    "a missing Status fails",
    any(
        "Status" in p
        for p in h5_problems(
            "docs/adr/0013-no-status.md", VALID_ADR.replace("- **Status:** Proposed\n", "")
        )
    ),
)
check(
    "a missing Context fails",
    any(
        "Context" in p
        for p in h5_problems(
            "docs/adr/0013-no-context.md",
            VALID_ADR.replace("## Context and Problem Statement", "## Background"),
        )
    ),
)
check(
    "a missing Decision fails",
    any(
        "Decision" in p
        for p in h5_problems(
            "docs/adr/0013-no-decision.md", VALID_ADR.replace("## Decision Outcome", "## Outcome")
        )
    ),
)
check(
    "a missing Consequences fails",
    any(
        "Consequences" in p
        for p in h5_problems(
            "docs/adr/0013-no-consequences.md", VALID_ADR.replace("## Consequences", "## Notes")
        )
    ),
)
check(
    "a title heading that does not carry its own number fails",
    any(
        "does not carry" in p
        for p in h5_problems(
            "docs/adr/0013-wrong-title.md", VALID_ADR.replace("# 0013.", "# 0007.")
        )
    ),
)
check(
    "the minimal MADR dialect passes too",
    h5_problems(
        "docs/adr/0013-minimal-dialect.md",
        "# ADR-0013: A decision\n\n- Status: Proposed\n- Date: 2026-09-20\n\n"
        "## Context\n\nx\n\n## Decision\n\ny\n\n## Consequences\n\nz\n",
    )
    == [],
)

# --- H5: the hook contract end to end ---------------------------------------------------------
h5_ok = run_hook("adr_structure_guard.py", write_event("docs/adr/0013-a-good-record.md", VALID_ADR))
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
check("the twelve historical records are present", len(HISTORY) == 12)
BEFORE = {f.name: f.read_bytes() for f in HISTORY}
for _event in (
    write_event("docs/adr/0013-a-good-record.md", VALID_ADR),
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
    not (ROOT / "docs/adr/0013-a-good-record.md").exists(),
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

# --- real Git worktree: the enforcement path, proven against an actual worktree ----------------
# Phase 7 found that a governed write made from a Git worktree was not detected. Paths were
# normalized against CLAUDE_PROJECT_DIR alone, so an absolute path under a worktree root kept the
# worktree prefix ('.claude/worktrees/<name>/...', or a temporary directory) and matched no
# governed prefix - H2, H3 and H5 all returned 0 for a write they exist to stop.
#
# These checks create REAL worktrees with 'git worktree add' and exercise the guards' own entry
# points against them. Nothing here re-implements normalization: the assertions are on what a guard
# decides and on the exit code a hook returns, so a regression in normalization fails them.

WORKTREE_CASES = (
    ("H2", h2, "db_migration_guard.py", "ragcore/migrations/versions/0026_worktree_probe.py"),
    ("H3", h3, "langgraph_change_guard.py", "ragcore/src/ragcore/graph/builder.py"),
    ("H5", h5, "adr_structure_guard.py", "docs/adr/9999-worktree-probe.md"),
)
UNGOVERNED_PROBE = "ragcore/src/ragcore/retrieval/hybrid.py"


def detects(guard, path: str) -> bool:
    """Whether this guard considers ``path`` governed, asked through the guard's own entry point."""
    if guard is h5:
        return h5.is_governed(path)
    return guard_hits(guard, edit_event(path)) != []


@contextmanager
def working_in(directory: Path, project_dir_value: str | None):
    """Run the body as Claude would: this working directory, this CLAUDE_PROJECT_DIR (or none)."""
    previous_cwd = Path.cwd()
    previous_env = os.environ.get("CLAUDE_PROJECT_DIR")
    os.chdir(directory)
    if project_dir_value is None:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
    else:
        os.environ["CLAUDE_PROJECT_DIR"] = project_dir_value
    reset_root_cache()
    try:
        yield
    finally:
        os.chdir(previous_cwd)
        if previous_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = previous_env
        reset_root_cache()


def git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )


def run_guard(
    script: str, args: list[str], cwd: Path, project_dir_value: str | None, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    """Run a guard exactly as settings.json does: the primary checkout's script, from ``cwd``."""
    env = dict(os.environ)
    if project_dir_value is None:
        env.pop("CLAUDE_PROJECT_DIR", None)
    else:
        env["CLAUDE_PROJECT_DIR"] = project_dir_value
    return subprocess.run(
        [sys.executable, str(HOOKS / script), *args],
        input=stdin,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def remove_tree(location: Path, attempts: int = 6) -> bool:
    """Delete a directory, retrying briefly.

    On Windows a checkout this suite has just read can hold transient handles - an indexer, a
    virus scanner, a file the interpreter has not released yet - and a single rmtree loses the
    race. Retrying makes cleanup deterministic instead of making the assertion tolerant.
    """

    def force_writable(func, path, _exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    for attempt in range(attempts):
        if not location.exists():
            return True
        shutil.rmtree(location, onerror=force_writable)
        if not location.exists():
            return True
        time.sleep(0.2 * (attempt + 1))
    return not location.exists()


def as_absolute(root: Path, relative: str) -> str:
    return str(root / relative).replace(chr(92), "/")


check("the fix names no local filesystem path", "D:/Projects" not in (HOOKS / "_guardlib.py")
      .read_text(encoding="utf-8"))

_temp_parent = Path(tempfile.mkdtemp(prefix="synthia-guard-worktree-"))
EXTERNAL_WT = _temp_parent / "external-checkout"
NESTED_WT = ROOT / ".claude" / "worktrees" / "guard-regression-probe"
_created: list[Path] = []

try:
    # A previous run that was interrupted can leave a probe behind. Clear it first: a stale
    # directory would fail 'worktree add' and make this suite report a defect it does not have.
    for _location in (EXTERNAL_WT, NESTED_WT):
        if _location.exists():
            git("worktree", "remove", "--force", str(_location))
            remove_tree(_location)
    git("worktree", "prune")

    for _label, _location in (("external", EXTERNAL_WT), ("nested", NESTED_WT)):
        _result = git("worktree", "add", "--detach", str(_location), "HEAD")
        _ok = _result.returncode == 0 and (_location / ".git").exists()
        check(f"a real {_label} Git worktree was created", _ok)
        if _ok:
            _created.append(_location)

    # A linked worktree's .git is a FILE, not a directory. That is the distinction the old
    # normalization missed, and the one the fix keys on.
    for _location in _created:
        check(
            f"the worktree at {_location.name} is a linked worktree (.git is a file)",
            (_location / ".git").is_file(),
        )

    ROOTS: list[tuple[str, Path]] = [("main checkout", ROOT)]
    ROOTS += [
        (("external worktree" if wt == EXTERNAL_WT else "nested worktree"), wt) for wt in _created
    ]

    # --- the regression matrix: root x path form x CLAUDE_PROJECT_DIR presence ----------------
    for _root_label, _root in ROOTS:
        for _env_label, _env_value in (
            ("CLAUDE_PROJECT_DIR set", str(ROOT)),
            ("CLAUDE_PROJECT_DIR absent", None),
        ):
            with working_in(_root, _env_value):
                for _name, _guard, _script, _path in WORKTREE_CASES:
                    for _form, _named in (
                        ("relative", _path),
                        ("absolute", as_absolute(_root, _path)),
                    ):
                        check(
                            f"{_name} detects a {_form} governed path "
                            f"from the {_root_label} ({_env_label})",
                            detects(_guard, _named),
                        )
                    for _form, _named in (
                        ("relative", UNGOVERNED_PROBE),
                        ("absolute", as_absolute(_root, UNGOVERNED_PROBE)),
                    ):
                        check(
                            f"{_name} leaves a {_form} non-governed path alone "
                            f"from the {_root_label} ({_env_label})",
                            not detects(_guard, _named),
                        )

    # --- the hook does not always run from the root of the tree --------------------------------
    # A Bash tool call can change directory, so a guard may run with cwd inside the tree. The
    # governed prefixes are repository-relative literals and must never be resolved against that
    # cwd; the path under test must be recognised whether it was written relative to the
    # subdirectory, relative to the repository, or absolute.
    SUBDIR_CASES = (
        ("H2", h2, "ragcore", "migrations/versions/0026_worktree_probe.py",
         "ragcore/migrations/versions/0026_worktree_probe.py"),
        ("H3", h3, "ragcore", "src/ragcore/graph/builder.py",
         "ragcore/src/ragcore/graph/builder.py"),
        ("H5", h5, "docs", "adr/9999-worktree-probe.md", "docs/adr/9999-worktree-probe.md"),
    )
    for _root_label, _root in ROOTS:
        for _name, _guard, _subdir, _sub_relative, _repo_relative in SUBDIR_CASES:
            _where = _root / _subdir
            if not _where.is_dir():
                continue
            for _env_label, _env_value in (
                ("CLAUDE_PROJECT_DIR set", str(ROOT)),
                ("CLAUDE_PROJECT_DIR absent", None),
            ):
                with working_in(_where, _env_value):
                    check(
                        f"{_name} detects a subdirectory-relative path from "
                        f"{_root_label}/{_subdir} ({_env_label})",
                        detects(_guard, _sub_relative),
                    )
                    check(
                        f"{_name} detects a repository-relative path from "
                        f"{_root_label}/{_subdir} ({_env_label})",
                        detects(_guard, _repo_relative),
                    )
                    check(
                        f"{_name} detects an absolute path from "
                        f"{_root_label}/{_subdir} ({_env_label})",
                        detects(_guard, as_absolute(_root, _repo_relative)),
                    )
                    check(
                        f"{_name} leaves a non-governed path alone from "
                        f"{_root_label}/{_subdir} ({_env_label})",
                        not detects(_guard, as_absolute(_root, UNGOVERNED_PROBE)),
                    )

    # --- the hook contract end to end, from a real worktree ------------------------------------
    # The precise Phase 7 bypass: cwd is the worktree, the path is absolute under it, and
    # CLAUDE_PROJECT_DIR still names the primary checkout. Exit 2 is the block.
    for _root_label, _root in ROOTS[1:]:
        for _name, _guard, _script, _path in WORKTREE_CASES:
            _blocked = run_guard(
                _script, [], _root, str(ROOT), json.dumps(edit_event(as_absolute(_root, _path)))
            )
            check(
                f"{_name} exits 2 for an absolute governed write from the {_root_label}",
                _blocked.returncode == 2,
            )
            check(
                f"{_name} explains itself when it blocks from the {_root_label}",
                _blocked.stderr.strip() != "",
            )
        _passed = run_guard(
            "db_migration_guard.py",
            [],
            _root,
            str(ROOT),
            json.dumps(edit_event(as_absolute(_root, UNGOVERNED_PROBE))),
        )
        check(f"a non-governed write from the {_root_label} exits 0", _passed.returncode == 0)

    # --- planted violations: written to disk in a real worktree, then removed -------------------
    # --diff reads the working tree of the root in use. Before the fix it read the primary
    # checkout, so a violation planted in a worktree was invisible to it.
    if _created:
        _wt = _created[0]
        PLANTED = {
            "db_migration_guard.py": (
                "ragcore/migrations/versions/0026_planted_violation.py",
                '"""Planted by test_guards.py. Removed before the suite exits."""\n',
            ),
            "langgraph_change_guard.py": (
                "ragcore/src/ragcore/graph/planted_violation.py",
                '"""Planted by test_guards.py. Removed before the suite exits."""\n',
            ),
            "adr_structure_guard.py": (
                "docs/adr/9999-planted-violation.md",
                "# A planted record with no number, no status and no sections\n",
            ),
        }

        # Clean first: nothing planted, nothing reported.
        for _script, (_relative, _body) in PLANTED.items():
            _clean = run_guard(_script, ["--diff"], _wt, str(ROOT))
            check(
                f"{_script} reports nothing for {_relative} before it is planted",
                _relative not in _clean.stdout,
            )

        try:
            for _script, (_relative, _body) in PLANTED.items():
                _file = _wt / _relative
                _file.parent.mkdir(parents=True, exist_ok=True)
                _file.write_text(_body, encoding="utf-8")

            for _script, (_relative, _body) in PLANTED.items():
                _seen = run_guard(_script, ["--diff"], _wt, str(ROOT))
                check(
                    f"{_script} reports the violation planted at {_relative} in a real worktree",
                    _relative in _seen.stdout,
                )

            # H5 validates the planted record's structure against the worktree's own history.
            _checked = run_guard(
                "adr_structure_guard.py",
                ["--check", PLANTED["adr_structure_guard.py"][0]],
                _wt,
                str(ROOT),
            )
            check("H5 rejects the planted record from a worktree", _checked.returncode == 1)
            for _expected in ("status", "context", "decision", "consequences"):
                check(
                    f"H5 names the missing '{_expected}' in the planted record",
                    _expected in _checked.stdout.lower(),
                )
        finally:
            for _script, (_relative, _body) in PLANTED.items():
                (_wt / _relative).unlink(missing_ok=True)

        # Restored: the tree is clean again and every guard says so.
        for _script, (_relative, _body) in PLANTED.items():
            _restored = run_guard(_script, ["--diff"], _wt, str(ROOT))
            check(
                f"{_script} reports nothing again once {_relative} is removed",
                _relative not in _restored.stdout,
            )
finally:
    for _location in _created:
        git("worktree", "remove", "--force", str(_location))
        # 'worktree remove' unregisters; on Windows it can leave the directory behind.
        remove_tree(_location)
    git("worktree", "prune")
    remove_tree(_temp_parent)

check(
    "every temporary worktree was removed",
    not EXTERNAL_WT.exists() and not NESTED_WT.exists(),
)

# --- no retired governance material is depended on, or present -------------------------------
# GOVERNED INVERSION. Earlier phases asserted that the migration inputs were still PRESENT so they
# could not be removed by accident mid-migration. They are now retired, so the invariant is the
# opposite one and is strictly harder to satisfy than silence:
#
#     Nothing in this repository reads, loads, cites or depends on retired governance material.
#
# The subject of the old assertions is what the repository deliberately retired. That makes this an
# inversion, not a weakened test (.claude/rules/40-testing.md 40.1): nothing is deleted, skipped or
# loosened.

RETIRED_PATHS = [".specify", "specs", "principles.yaml", "dotnet.yaml", "dotnet_lang.yaml",
                 "python.yaml", "python_lang.yaml", "docs/migration"]
for _rp in RETIRED_PATHS:
    check("retired from the tree: " + _rp, not (ROOT / _rp).exists())

speckit_skills = sorted((ROOT / ".claude/skills").glob("speckit-*"))
check("no speckit-* skill remains: " + (", ".join(p.name for p in speckit_skills) or "none"),
      not speckit_skills)

SKILL_DIRS = sorted(p for p in (ROOT / ".claude/skills").iterdir() if p.is_dir())
check("exactly the four Claude governance skills remain: "
      + ", ".join(p.name for p in SKILL_DIRS),
      [p.name for p in SKILL_DIRS]
      == ["adr-author", "db-change", "functional-update", "langgraph-change"])
for _skill in SKILL_DIRS:
    check(f"{_skill.name} is a skill (carries SKILL.md)", (_skill / "SKILL.md").is_file())

# The live governance surface: .claude/, CLAUDE.md, and the two permanent governance documents.
# test_guards.py excludes itself because it necessarily contains the patterns it searches for; it
# is asserted separately below.
LIVE_CLAUDE = sorted(
    p for p in (ROOT / ".claude").rglob("*")
    if p.is_file()
    and "__pycache__" not in p.parts
    and "worktrees" not in p.parts
    and p.name != "settings.local.json"
    and p.name != "test_guards.py"
    and not p.name.endswith(".tmp")
)
CLAUDE_MD_PATH = ROOT / "CLAUDE.md"
GOVERNANCE_DOCS = [ROOT / "docs/final-repository-governance.md", ROOT / "docs/governance/open-items.md"]
LIVE_SURFACE = LIVE_CLAUDE + [CLAUDE_MD_PATH] + [d for d in GOVERNANCE_DOCS if d.is_file()]

# (1) nothing on the live surface names a retired artifact at all. There is no longer a "mentions
# it only to deny it" exemption: the artifacts are gone, so a reader who meets the name has
# nothing to look at, and a pointer to nothing is worse than silence.
RETIRED_NAME = re.compile(
    r"\.specify|speckit|spec kit|constitution|docs/migration|"
    r"principles\.yaml|dotnet_?l?a?n?g?\.yaml|python_?l?a?n?g?\.yaml", re.I)
_stale = []
for _p in LIVE_SURFACE:
    _t = _p.read_text(encoding="utf-8", errors="replace")
    if RETIRED_NAME.search(_t):
        _stale.append(str(_p.relative_to(ROOT)).replace(chr(92), "/"))
check("no live governance file names a retired artifact: "
      + (", ".join(_stale[:5]) or "clean"), not _stale)

# (2) the committed hook configuration invokes nothing retired
_settings_raw = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
check("settings.json invokes no retired command",
      not RETIRED_NAME.search(_settings_raw))

# (3) the guard suite itself loads nothing retired. It cannot usefully search itself for the
# presence of its own search patterns, so the positive invariant -- that it asserts the ABSENCE of
# the artifacts -- is the RETIRED_PATHS block above rather than a self-referential string match.
_self = Path(__file__).read_text(encoding="utf-8")
check("the guard suite runs no retired script",
      not re.search(r"\.specify/(scripts|templates)", _self))

# (4) no tracked file anywhere in the repository cites a retired governance artifact by name.
# Established with git ls-files, not by walking the tree: build residue is not repository content
# (.claude/rules/90-functional-knowledge.md 90.2).
_tracked_all = git("ls-files").stdout.splitlines()
# docs/adr/** is excluded on purpose: an accepted record is never reworded, renumbered or
# retro-statused (.claude/rules/70-adr.md 70.6). A record that cited a document which has since
# been retired is history doing its job, not a stale pointer to repair. The same holds for
# docs/architecture/integrations-service-delta.md, which is a non-authoritative historical delta.
HISTORY = ("docs/adr/", "docs/architecture/integrations-service-delta.md")
_cited = []
for _rel in _tracked_all:
    if _rel.startswith(".claude/hooks/test_guards.py") or _rel.startswith(HISTORY):
        continue
    _f = ROOT / _rel
    if not _f.is_file() or _f.stat().st_size > 400_000:
        continue
    if _f.suffix.lower() in (".png", ".ico", ".lock", ".svg"):
        continue
    try:
        _t = _f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    if re.search(r"\.specify|speckit|\bconstitution\b|docs/migration/", _t, re.I):
        _cited.append(_rel)
check("no tracked file cites a retired governance artifact: "
      + (", ".join(_cited[:6]) or "clean"), not _cited)

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

# --- the three architecture authorities exist, and nothing else claims to be one ---------------
# .claude/rules/00-authority.md 00.2: exactly three documents are architecture authority. The list
# is closed, so both halves are asserted -- the three are present, and the two files that sit in
# the same directory without authority are named as carrying none.

ARCHITECTURE = [
    "docs/architecture/identity-plane-final.md",
    "docs/architecture/Synthia-OverallArchitecture-final.md",
    "docs/architecture/RagAgent-Architecture-final.md",
]
NOT_AUTHORITY = [
    "docs/architecture/integrations-service-delta.md",
    "docs/architecture/ragcore-langgraph-flow.md",
]
for _a in ARCHITECTURE:
    check("architecture authority present: " + _a, (ROOT / _a).is_file())

AUTHORITY_RULE = (ROOT / ".claude/rules/00-authority.md").read_text(encoding="utf-8")
for _a in ARCHITECTURE:
    check("00-authority.md names " + Path(_a).name, Path(_a).name in AUTHORITY_RULE)
for _n in NOT_AUTHORITY:
    check("00-authority.md denies authority to " + Path(_n).name, Path(_n).name in AUTHORITY_RULE)
check("00-authority.md states the closed list", "Exactly three documents" in AUTHORITY_RULE
      or "exactly three documents" in AUTHORITY_RULE.lower())
check("00-authority.md keeps the baseline in .claude/rules",
      ".claude/rules/**` is the engineering baseline" in AUTHORITY_RULE)
check("00-authority.md states that approval is never inferred",
      "00.10 Approval and acceptance are never inferred" in AUTHORITY_RULE)

# --- the rule set is complete and well formed --------------------------------------------------
# The fourteen files below are the whole engineering baseline. A missing one is a governance area
# with no rule; an extra one is an authority nobody decided to create.

REQUIRED_RULES = [
    "00-authority.md", "10-principles.md", "20-dotnet.md", "21-python.md",
    "22-web-typescript.md", "23-angular.md", "24-electron.md", "30-langgraph.md",
    "40-testing.md", "50-database.md", "60-architecture-gates.md", "70-adr.md",
    "80-security-ops.md", "90-functional-knowledge.md",
]
RULE_TEXT = {p.name: p.read_text(encoding="utf-8")
             for p in sorted((ROOT / ".claude/rules").glob("*.md"))}
check("exactly the fourteen rule files exist: " + ", ".join(sorted(RULE_TEXT)),
      sorted(RULE_TEXT) == REQUIRED_RULES)

for _name, _text in sorted(RULE_TEXT.items()):
    _prose = outside_fences(_text)
    check(_name + " has a single H1", _prose.count("\n# ") + _prose.startswith("# ") == 1)
    check(_name + " has balanced code fences", _text.count("```") % 2 == 0)

ALL_RULES = "\n".join(RULE_TEXT.values())

# every rule file that governs one stack says so, and says which paths
check("20-dotnet.md declares its stack", "governs `.NET / C#` code only" in RULE_TEXT["20-dotnet.md"])
check("20-dotnet.md names its paths", "`dotnet/**`" in RULE_TEXT["20-dotnet.md"])
check("21-python.md declares its stack", "governs Python code only" in RULE_TEXT["21-python.md"])
check("21-python.md names its paths", "`ragcore/**`" in RULE_TEXT["21-python.md"]
      and "`integrations/**`" in RULE_TEXT["21-python.md"])
check("22-web-typescript.md names its paths", "`apps/web/**`" in RULE_TEXT["22-web-typescript.md"]
      and "`apps/desktop/**`" in RULE_TEXT["22-web-typescript.md"])
check("no language rule silently claims another stack",
      "language-independent" not in RULE_TEXT["20-dotnet.md"].split("## 20.1")[0])

# --- path-scoped rules parse, and their globs name real, tracked directories -------------------
SCOPED: dict[str, list[str]] = {}
for _p in sorted((ROOT / ".claude/rules").glob("*.md")):
    _t = _p.read_text(encoding="utf-8")
    if not _t.startswith("---\n"):
        continue
    _end = _t.find("\n---\n", 3)
    check(_p.name + " frontmatter is terminated", _end != -1)
    if _end == -1:
        continue
    _fm = _t[4:_end]
    _globs = re.findall(r'^\s*-\s*"([^"]+)"\s*$', _fm, re.M)
    check(_p.name + " frontmatter declares a paths list",
          _fm.lstrip().startswith("paths:") and bool(_globs))
    check(_p.name + " has exactly one H1 after its frontmatter",
          _t[_end + 5:].lstrip().startswith("# "))
    SCOPED[_p.name] = _globs

check("exactly the five language/stack rules are path-scoped: " + ", ".join(sorted(SCOPED)),
      sorted(SCOPED) == ["20-dotnet.md", "21-python.md", "22-web-typescript.md",
                         "23-angular.md", "24-electron.md"])

_tracked = git("ls-files").stdout.splitlines()
for _name, _globs in sorted(SCOPED.items()):
    for _g in _globs:
        _prefix = _g.split("*")[0].rstrip("/")
        check(f"{_name} scope '{_g}' names a real directory",
              bool(_prefix) and (ROOT / _prefix).is_dir())
        check(f"{_name} scope '{_g}' matches tracked files",
              any(f.startswith(_prefix + "/") for f in _tracked))

# a governance/gate rule stays unscoped: a gate is detected BEFORE a file is opened, so scoping
# one to the paths it governs would load it only after the moment it exists to catch.
for _global in ("00-authority.md", "10-principles.md", "30-langgraph.md", "40-testing.md",
                "50-database.md", "60-architecture-gates.md", "70-adr.md",
                "80-security-ops.md", "90-functional-knowledge.md"):
    check("governance rule stays repository-wide: " + _global, _global not in SCOPED)

# --- rule identifiers are defined here, once each, and nowhere else ---------------------------
# .claude/rules/00-authority.md 00.3 states the identifier spaces and says the rule files define
# them. These checks prove that: every space is populated, and every requirement that carries an
# id is defined under exactly one heading.

ID_SPACES = {
    "P-": ("10-principles.md", r"^### (P-\d+) ", 32),
    "C-": ("10-principles.md", r"^### (C-\d+) ", 6),
    "H-": ("10-principles.md", r"^### (H-\d+) ", 2),
    "TC-": ("40-testing.md", r"\| \*\*(TC-\d+)\*\*", 15),
    "CM-": ("40-testing.md", r"\| \*\*(CM-\d+)\*\*", 12),
}
for _prefix, (_file, _pat, _expected) in sorted(ID_SPACES.items()):
    _ids = re.findall(_pat, RULE_TEXT[_file], re.M)
    check(f"{_prefix}* is defined in {_file}: {len(_ids)} of {_expected}", len(_ids) == _expected)
    check(f"{_prefix}* carries no duplicate definition", len(set(_ids)) == len(_ids))

check("00-authority.md documents every identifier space",
      all(s in AUTHORITY_RULE for s in ("`P-1`", "`C-1`", "`H-1`", "`DN-1`", "`PY-1`",
                                        "`BL-01`", "`TC-01`", "`CM-01`")))
check("00-authority.md explains Origin lines as provenance, not authority",
      "Origin line is provenance" in AUTHORITY_RULE)

# the frontend baseline: every FE-* requirement is defined under exactly one heading
FRONTEND_RULES = ("22-web-typescript.md", "23-angular.md", "24-electron.md")
_fe_text = "\n".join(RULE_TEXT[_n] for _n in FRONTEND_RULES)
FE_IDS = sorted(set(re.findall(r"\bFE-(?:SH|TS|NG|EL)-\d+\b", _fe_text)))
check(f"the frontend baseline carries requirement ids ({len(FE_IDS)} found)", len(FE_IDS) >= 20)
for _fid in FE_IDS:
    check("frontend requirement is defined under exactly one heading: " + _fid,
          len(re.findall(r"^### " + _fid + r" ", _fe_text, re.M)) == 1)
check("every frontend rule file states Origin lines",
      all("*Origin:" in RULE_TEXT[_n] for _n in FRONTEND_RULES))
check("every frontend rule file states enforcement honestly",
      all("Enforcement:" in RULE_TEXT[_n] for _n in FRONTEND_RULES))
check("every frontend rule file names the ADR that authorized it",
      all("0010-frontend-engineering-baseline.md" in RULE_TEXT[_n] for _n in FRONTEND_RULES))
check("the frontend baseline declares itself the authority",
      "THE FRONTEND BASELINE IS AUTHORITATIVE" in RULE_TEXT["22-web-typescript.md"])
check("committed frontend tooling is still not promoted to baseline authority",
      "evidence of what is, not authority for what should be"
      in RULE_TEXT["22-web-typescript.md"])
check("the superseded 'no baseline defined' statement is gone from the rules",
      "TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED" not in ALL_RULES)

# --- enforcement is claimed with the honest vocabulary, never rounded up ----------------------
# The four honest labels, plus "not-applicable" for a row where the rule cannot apply to that
# stack at all. A claim may also discharge itself by naming the rule whose enforcement it shares,
# or by naming the registered deviation that explains why the gate is absent - both are honest
# statements about the gate, which is what this check exists to hold.
VOCAB = ("mechanical", "partial", "procedural", "currently-unenforced", "not-applicable",
         "see DN-", "see PY-", "see BL-", "see FE-", "deviation ")
for _name, _text in sorted(RULE_TEXT.items()):
    if "Enforcement:" not in _text:
        continue
    _clauses = [m.group(1) for m in re.finditer(r"Enforcement:(.{0,160})", _text, re.S)]
    _bad = [c.strip()[:48] for c in _clauses if not any(v in c for v in VOCAB)]
    check(f"{_name} states every enforcement claim in the honest vocabulary: "
          + (", ".join(_bad[:3]) or "clean"), not _bad)
for _rule, _file in (("lang/dotnet#DN8", "20-dotnet.md"), ("lang/dotnet#DN31", "20-dotnet.md"),
                     ("lang/python#PY4", "21-python.md")):
    check(_rule + " is recorded as unenforced, not claimed green",
          "currently-unenforced" in RULE_TEXT[_file])

# --- every path a rule or CLAUDE.md cites actually exists -------------------------------------
CLAUDE_MD = ROOT / "CLAUDE.md"
check("exists: CLAUDE.md", CLAUDE_MD.is_file())
claude_text = CLAUDE_MD.read_text(encoding="utf-8") if CLAUDE_MD.is_file() else ""
GOV_DOC = ROOT / "docs/final-repository-governance.md"
OPEN_ITEMS = ROOT / "docs/governance/open-items.md"
check("exists: docs/final-repository-governance.md", GOV_DOC.is_file())
check("exists: docs/governance/open-items.md", OPEN_ITEMS.is_file())
gov_text = GOV_DOC.read_text(encoding="utf-8") if GOV_DOC.is_file() else ""
open_items = OPEN_ITEMS.read_text(encoding="utf-8") if OPEN_ITEMS.is_file() else ""

_refs = set()
for _text in list(RULE_TEXT.values()) + [claude_text, gov_text, open_items]:
    for _m in re.finditer(r"`((?:\.claude|docs|build|azure-pipelines|apps|dotnet|ragcore|"
                          r"integrations)/[A-Za-z0-9_./-]+)`", _text):
        _refs.add(_m.group(1))
# A citation like `docs/adr/0001` names a record by number, and `docs/adr/NNNN` is the filename
# grammar. Neither is a path, so only references carrying a file extension are resolved.
_broken = sorted(r for r in _refs
                 if "*" not in r and "<" not in r and not r.endswith("/")
                 and "NNNN" not in r and Path(r).suffix
                 and not (ROOT / r).exists())
check("every repository path cited by the governance surface exists: "
      + (", ".join(_broken[:6]) or "all resolve"), not _broken)

# --- CLAUDE.md is permanent project guidance, and routes rather than restates -----------------
check("CLAUDE.md is concise", 0 < len(claude_text.splitlines()) <= 320)
for _doc in ARCHITECTURE:
    check("CLAUDE.md names architecture authority " + Path(_doc).name,
          Path(_doc).name in claude_text)
for _gate in ("50-database.md", "30-langgraph.md", "70-adr.md", "90-functional-knowledge.md"):
    check("CLAUDE.md names the gate " + _gate, _gate in claude_text)
_listed = [n for n in RULE_TEXT if n in claude_text]
check("CLAUDE.md indexes every rule file", len(_listed) == len(RULE_TEXT))
check("CLAUDE.md names docs/functional/implemented.md",
      "docs/functional/implemented.md" in claude_text)
check("CLAUDE.md names the open-items register", "docs/governance/open-items.md" in claude_text)
check("CLAUDE.md names the permanent governance document",
      "docs/final-repository-governance.md" in claude_text)
check("CLAUDE.md distinguishes rules from skills",
      ".claude/rules/" in claude_text and ".claude/skills/" in claude_text)
check("CLAUDE.md does not inline the baseline", "principles#P1" not in claude_text)
check("CLAUDE.md states the conformance gate before code generation",
      "STOP before generating code" in claude_text)
check("CLAUDE.md states that approval is never inferred",
      "never inferred" in claude_text.lower())
check("CLAUDE.md states the functional-truth ordering",
      "THEN update implemented.md" in claude_text)
check("CLAUDE.md carries the language governance matrix",
      "## 9. Language governance" in claude_text)
check("CLAUDE.md carries the MCP section", "## 13. MCP tooling" in claude_text)
check("CLAUDE.md names the next ADR number",
      "next: 0013" in claude_text or "**next: 0013**" in claude_text)
check("CLAUDE.md reads as durable guidance, not a migration diary",
      not re.search(r"\bPhase \d+\b", claude_text))

# --- language governance: no executable language is left without a governing rule -------------
# Derived from what is TRACKED, not from a list somebody maintains by hand: a new language enters
# this check the moment its first file is committed.
LANGUAGE_BY_SUFFIX = {
    ".cs": "C#", ".py": "Python", ".ts": "TypeScript", ".js": "JavaScript", ".mjs": "JavaScript",
    ".html": "HTML", ".css": "CSS", ".sh": "Shell", ".ps1": "PowerShell", ".sql": "SQL",
}
GOVERNED_LANGUAGES = {
    "C#": "C#", "Python": "Python", "TypeScript": "TypeScript", "JavaScript": "JavaScript",
    "HTML": "HTML", "CSS": "CSS", "Shell": "Shell", "PowerShell": "PowerShell", "SQL": "SQL",
}
_present = sorted({LANGUAGE_BY_SUFFIX[Path(f).suffix.lower()] for f in _tracked
                   if Path(f).suffix.lower() in LANGUAGE_BY_SUFFIX})
check("every tracked executable language is known: " + ", ".join(_present),
      all(lang in GOVERNED_LANGUAGES for lang in _present))
_lang_section = claude_text.split("## 9. Language governance")[-1].split("## 10.")[0]
_ungoverned = [lang for lang in _present if GOVERNED_LANGUAGES[lang] not in _lang_section]
check("every tracked executable language appears in the language matrix: "
      + (", ".join(_ungoverned) or "all governed"), not _ungoverned)
check("the language matrix names a governing rule file for each row",
      _lang_section.count("`2") >= 5)
check("the language matrix states that a new language needs a rule first",
      "needs a governing rule **before** it carries logic" in _lang_section)

# --- the permanent governance document points, and does not become a second baseline ----------
for _needle in ("identity-plane-final.md", "Synthia-OverallArchitecture-final.md",
                "RagAgent-Architecture-final.md", ".claude/rules/**",
                "docs/functional/implemented.md", "docs/governance/open-items.md",
                "azure-pipelines/", "Serena", "Figma"):
    check("final-repository-governance.md points at " + _needle, _needle in gov_text)
check("final-repository-governance.md denies itself authority",
      "not authority for anything" in gov_text)
check("final-repository-governance.md stays short",
      0 < len(gov_text.splitlines()) <= 200)
check("final-repository-governance.md does not restate a rule body",
      "P-1 —" not in gov_text and "DN-8 —" not in gov_text)

# --- the open-items register: everything a rule says is open is actually registered ------------
# A deviation that a rule mentions but nothing registers is a deviation nobody tracks. A register
# row nobody cites is a row that drifts. Both directions are asserted.

for _heading in ("## 1. Deviations", "## 2. Enforcement gaps",
                 "## 3. Conflicts between authoritative sources",
                 "## 4. Defects in retired inputs",
                 "## 5. Cross-stack citation gap",
                 "## 6. Human decisions",
                 "## 7. Conformance findings",
                 "## 8. Recorded test obligations that are not met"):
    check("open-items register has " + _heading, _heading in open_items)
check("the open-items register denies itself authority",
      "Not authority" in open_items)
check("the open-items register forbids closing a row on Claude's own initiative",
      "do not mark one closed on Claude's own initiative" in open_items)

_cited_ids = sorted({m for m in re.findall(r"\*\*((?:DV|EG|UD|CF|D|FE-AMB)-\d+)\*\*", ALL_RULES)})
_unregistered = [i for i in _cited_ids if i not in open_items]
check("every open item a rule cites is registered: "
      + (", ".join(_unregistered[:6]) or "all registered"), not _unregistered)
for _must in ("DV-1", "DV-10", "DV-11", "EG-1", "EG-2", "EG-6", "EG-10", "CF-2", "UD-8"):
    check("open item survives in the register: " + _must, "**" + _must + "**" in open_items)
check("the closed conflict is not silently re-opened", "CF-1 is closed" in open_items)
check("the register states the conformance findings without resolving them",
      "Reported, never reconciled" in open_items)

# --- the four gates still say what they are for -----------------------------------------------
for _f in (ROOT / ".claude/rules/30-langgraph.md", ROOT / ".claude/rules/50-database.md",
           ROOT / ".claude/rules/70-adr.md"):
    _text = _f.read_text(encoding="utf-8")
    check(_f.name + " forbids inferred approval", "infer" in _text.lower())
for _f in (ROOT / ".claude/rules/30-langgraph.md", ROOT / ".claude/rules/50-database.md"):
    _text = _f.read_text(encoding="utf-8")
    check(_f.name + " states the ordering",
          "DETECT" in _text and "STOP" in _text and "APPROVE" in _text)

db_rule = RULE_TEXT["50-database.md"]
for _needle in ("identity-bearing", "permission boundary", "checkpoint", "downgrade",
                "backfill", "nullability", "single head"):
    check("50-database.md covers " + _needle, _needle in db_rule.lower())
check("50-database.md keeps Alembic as the single mechanism",
      "Do not introduce EF Core migrations" in db_rule)

graph_rule = RULE_TEXT["30-langgraph.md"]
for _needle in ("execution_treatment", "interrupt", "resume", "termination", "side effect",
                "ADR", "tenant", "never owns execution authority", "checkpoint"):
    check("30-langgraph.md covers " + _needle, _needle in graph_rule)
check("30-langgraph.md still lists seventeen ADR triggers",
      "seventeen" in graph_rule or len(re.findall(r"^\d+\. \*\*", graph_rule, re.M)) >= 17)

adr_rule = RULE_TEXT["70-adr.md"]
check("70-adr.md states the ordering", all(w in adr_rule for w in ("DETECT", "STOP", "ACCEPT")))
for _needle in ("architecture change", "engineering-baseline change",
                "identity-bearing immutability", "permission boundar", "checkpoint persistence",
                "30-langgraph.md", "50-database.md", "madr", "status", "proposed",
                "sequential", "historical record", "never"):
    check("70-adr.md covers " + _needle, _needle in adr_rule.lower())
check("70-adr.md keeps writing and accepting separate",
      "Writing an ADR is not approval of it." in adr_rule)
check("70-adr.md does not duplicate the 30.4 trigger list",
      adr_rule.count("execution_treatment") <= 1)
check("70-adr.md names the three architecture documents",
      all(Path(d).name in adr_rule for d in ARCHITECTURE))
check("70-adr.md excludes the non-authoritative architecture files",
      all(Path(n).name in adr_rule for n in NOT_AUTHORITY))
check("70-adr.md names the next number", "0013" in adr_rule)

for _name, _needle in (("30-langgraph.md", "execution_treatment"),
                       ("50-database.md", "identity-bearing"),
                       ("70-adr.md", "MADR"),
                       ("90-functional-knowledge.md", "implemented.md")):
    check("pre-existing governance intact: " + _name, _needle in RULE_TEXT[_name])

# --- the skills are procedures, and never authority -------------------------------------------
SKILLS = [ROOT / ".claude/skills" / n / "SKILL.md"
          for n in ("db-change", "langgraph-change", "adr-author", "functional-update")]
for _f in SKILLS:
    check("exists: SKILL.md (" + _f.parent.name + ")", _f.is_file())
    text = _f.read_text(encoding="utf-8")
    check(_f.parent.name + " opens with frontmatter", text.startswith("---\n"))
    body = text.split("---\n", 2)
    check(_f.parent.name + " frontmatter closes", len(body) == 3)
    check(_f.parent.name + " frontmatter names the skill",
          'name: "' + _f.parent.name + '"' in body[1])
    check(_f.parent.name + " frontmatter has a description", "description:" in body[1])
    check(_f.parent.name + " has balanced code fences", body[2].count("```") % 2 == 0)
    check(_f.parent.name + " never self-approves",
          "never approve" in text.lower() or "must never do" in text.lower())

adr_skill = (ROOT / ".claude/skills/adr-author/SKILL.md").read_text(encoding="utf-8")
check("adr-author is procedural", adr_skill.count("## Step ") >= 9)
check("adr-author stops before implementation", "STOP" in adr_skill)
check("adr-author separates drafting from acceptance", "HUMAN ACCEPTANCE" in adr_skill.upper())
check("adr-author self-checks before stopping", "SELF-CHECK" in adr_skill.upper())
check("adr-author names the architecture owner", "owning document" in adr_skill)
check("adr-author refuses to choose an architecture for a human",
      "when the choice is a human's" in adr_skill)
check("adr-author defers the trigger lists to the rules", "70-adr.md" in adr_skill)

# --- the testing baseline: fifteen categories, twelve matrix rows, and the coverage policy -----
# These prove the requirement SURVIVES -- by meaning, not by count. A count check would pass
# against fifteen empty rows, so every category is matched on its id, its name AND the thing it
# proves.
TESTING = RULE_TEXT["40-testing.md"]

check("40-testing.md names the ADR that authorized the categories",
      "0011-required-test-categories-baseline.md" in TESTING)
check("40-testing.md is still the single testing-baseline authority",
      "testing-baseline authority" in TESTING)

REQUIRED_CATEGORIES = {
    "TC-01": ("Unit", "Component behaviour in isolation"),
    "TC-02": ("Integration", "Real collaborators, real database, real messaging"),
    "TC-03": ("Contract", "Published API and message shapes, including between deployables"),
    "TC-04": ("Authorization",
              "Every operation against every role set, including the empty intersection"),
    "TC-05": ("Tenant isolation", "No path returns another organisation"),
    "TC-06": ("Retrieval isolation",
              "The tenant filter cannot be evaded, including by crafted input"),
    "TC-07": ("Governance", "Treatment comes from the catalogue and never from model output"),
    "TC-08": ("Approval", "Binding, expiry, first-valid-verdict-wins, no synthesized verdict"),
    "TC-09": ("Idempotency", "At-least-once delivery produces exactly one effect"),
    "TC-10": ("Concurrency", "Concurrent claims and decisions resolve to one outcome"),
    "TC-11": ("Adapter", "Provider behaviour stays behind its boundary"),
    "TC-12": ("Architecture dependency",
              "Module boundaries, banned APIs, the no-cross-deployable-dependency rule"),
    "TC-13": ("Configuration validation", "Options bind, validate and fail fast at start"),
    "TC-14": ("Security", "are actually unreachable"),
    "TC-15": ("End-to-end golden path",
              "A representative journey completes through every layer"),
}
check("the baseline carries exactly fifteen categories, not sixteen",
      len(REQUIRED_CATEGORIES) == 15)
for _tc, (_name, _proves) in sorted(REQUIRED_CATEGORIES.items()):
    _row = [ln for ln in TESTING.splitlines() if ln.lstrip().startswith("| **" + _tc + "**")]
    check("required test category is defined exactly once: " + _tc + " " + _name, len(_row) == 1)
    if len(_row) == 1:
        check(_tc + " carries its category name: " + _name, _name in _row[0])
        check(_tc + " carries what it proves: " + _proves[:48], _proves in _row[0])
check("no sixteenth category was invented", "TC-16" not in TESTING)
check("the categories are stated as required and non-substitutable",
      "All fifteen are required; none substitutes for another" in TESTING)

check("a security or isolation fix owes a failing-then-passing test",
      "A security or isolation fix without a failing-then-passing test is incomplete" in TESTING)
check("the failing-then-passing order is stated, not merely named",
      "fails against the unfixed code and passes against the fixed code" in TESTING)

CHANGE_MATRIX = {
    "CM-01": ("Adds or alters an API endpoint or message shape", ("TC-03", "TC-04")),
    "CM-02": ("Adds or alters an authorization rule, role set or accepted-role declaration",
              ("TC-04", "TC-14")),
    "CM-03": ("Touches a query, repository, view or retrieval path", ("TC-05", "TC-06")),
    "CM-04": ("Adds or alters a catalogue entry, treatment policy or gate condition",
              ("TC-07", "TC-04")),
    "CM-05": ("Touches approval, consent, verdict or the resume path",
              ("TC-08", "TC-10", "TC-09")),
    "CM-06": ("Adds or alters an external side effect", ("TC-09", "TC-11")),
    "CM-07": ("Adds or alters a migration, table or published view",
              ("TC-02", "TC-05", "TC-12")),
    "CM-08": ("Adds or alters a module boundary, project reference or import", ("TC-12",)),
    "CM-09": ("Adds or alters a configuration option or secret reference", ("TC-13",)),
    "CM-10": ("Touches an outbox, trigger, claim or worker", ("TC-09", "TC-10")),
    "CM-11": ("Touches a client surface", ("TC-15",)),
    "CM-12": ("Fixes a security or isolation defect", ()),
}
check("the change matrix carries exactly twelve rows", len(CHANGE_MATRIX) == 12)
for _cm, (_desc, _owed) in sorted(CHANGE_MATRIX.items()):
    _row = [ln for ln in TESTING.splitlines() if ln.lstrip().startswith("| **" + _cm + "**")]
    check("change-matrix row is defined exactly once: " + _cm, len(_row) == 1)
    if len(_row) == 1:
        check(_cm + " states the change it matches: " + _desc[:44], _desc in _row[0])
        for _t in _owed:
            check(_cm + " still owes " + _t, _t in _row[0])
check("no thirteenth matrix row was invented", "CM-13" not in TESTING)

check("TC-01 Unit is explicitly owed by every change", "Unit is owed by every change" in TESTING)
check("the every-change rule explains why unit is absent from the rows",
      "not repeated below" in TESTING)
check("a change matching several rows owes all of their categories",
      "matching several rows owes all of their categories" in TESTING)
check("CM-12 carries the failing-first ordering",
      any("**CM-12**" in ln and "failing first, then passing" in ln
          for ln in TESTING.splitlines()))

_cm11 = next((ln for ln in TESTING.splitlines() if ln.lstrip().startswith("| **CM-11**")), "")
check("CM-11 points at the Angular rule for the frontend requirement",
      "23-angular.md" in _cm11 and "FE-NG-5" in _cm11 and "FE-NG-6" in _cm11)
check("CM-11 still owes the end-to-end golden path itself", "TC-15" in _cm11)
for _fe_body in ("WCAG 2.2 Level AA, on every surface", "The project-supported test runner"):
    check("the frontend requirement text is NOT duplicated into 40-testing.md: " + _fe_body,
          _fe_body not in TESTING)
check("FE-NG-5 and FE-NG-6 are still defined in 23-angular.md, once each",
      RULE_TEXT["23-angular.md"].count("### FE-NG-5 ") == 1
      and RULE_TEXT["23-angular.md"].count("### FE-NG-6 ") == 1)

check("no coverage threshold is set and none gates a merge",
      "No line- or branch-coverage threshold is set, and none gates a merge" in TESTING)
check("the absence of a threshold is stated as deliberate, not an omission",
      "This is deliberate, not" in TESTING and "omission" in TESTING)
check("coverage may be measured and reported as information",
      "may** be measured and reported as information" in TESTING)
check("coverage cannot become a merge gate without an accepted ADR",
      "must not** become a merge gate" in TESTING and "accepted ADR" in TESTING)
check("the coverage amendment path names the ADR trigger",
      "70-adr.md` §70.2 B(6)" in TESTING)
check("no coverage percentage threshold was introduced",
      not re.search(r"\d{1,3}\s*%\s*(?:line|branch|statement|coverage)", TESTING, re.I))

check("the recorded exception is labelled a gap, not a carve-out",
      "a gap, not a carve-out" in TESTING)
for _hf in ("tenant context derived from an untrusted client field", "authorization bypass"):
    check("the recorded hard-failure exception survives: " + _hf, _hf in TESTING)
check("the exception states the obligation is unchanged and simply NOT MET",
      "The obligation in §40.8 is unchanged" in TESTING and "NOT MET" in TESTING)
check("no weaker substitute test may be written to appear to meet it",
      "appears to meet it by asserting something weaker" in TESTING)
check("the exception points at the deferral it came from, without reopening it",
      "0008-defer-certificate-based-gateway-to-backend-provenance" in TESTING
      and "D-01" in TESTING)
check("the migrated categories are recorded as procedural, not claimed mechanical",
      "**procedural**" in TESTING)
check("EG-10 is recorded in the rule", "EG-10" in TESTING)
check("40-testing.md distinguishes what a principle owes from what a change owes",
      "what does this *principle* owe?" in TESTING and "what does this *change* owe?" in TESTING)
check("§40.5 is still the principle axis and was not absorbed",
      "## 40.5 Test kinds the baseline requires by name" in TESTING)
check("the gate-owned testing obligations are cross-referenced, not restated",
      all(_r in TESTING for _r in ("50-database.md` §50.8", "30-langgraph.md` §30.9",
                                   "70-adr.md` §70.8", "90-functional-knowledge.md` §90.10")))
check("the non-negotiable is untouched", "Never weaken a test to make a change pass" in TESTING)
# --- ADR governance: every record is structurally valid, indexed, and honestly statused --------
ADR_DIR = ROOT / "docs/adr"
ADR_RECORDS = sorted(p for p in ADR_DIR.glob("*.md") if p.name.lower() != "readme.md")
check("the ADR history is present: " + str(len(ADR_RECORDS)) + " records", len(ADR_RECORDS) >= 12)

for _rec in ADR_RECORDS:
    _rel = "docs/adr/" + _rec.name
    _problems = h5.validate(_rel, _rec.read_text(encoding="utf-8"), is_new=False)
    check("ADR is structurally valid: " + _rec.name + " " + ("; ".join(_problems) or ""),
          not _problems)

_numbers = sorted(int(p.name[:4]) for p in ADR_RECORDS)
check("ADR numbers are unique", len(set(_numbers)) == len(_numbers))
check("ADR numbering is gapless from 0001", _numbers == list(range(1, len(_numbers) + 1)))
_next = "%04d" % (_numbers[-1] + 1)
check("the next ADR number is one past the highest on disk, and the rule says so: " + _next,
      re.search(r"next[^.]{0,40}" + _next, adr_rule, re.I) is not None)

_idx = (ADR_DIR / "README.md").read_text(encoding="utf-8")
_idx_rows = re.findall(r"^\| \[(\d{4})\]\((\./[^)]+)\) \|[^|]*\| \*\*([A-Za-z ]+?)\*\*",
                       _idx, re.M)
check("the ADR index lists every record in ascending order: "
      + ", ".join(n for n, _, _ in _idx_rows),
      len(_idx_rows) == len(ADR_RECORDS)
      and [n for n, _, _ in _idx_rows] == sorted(n for n, _, _ in _idx_rows))
for _num, _rel, _shown in _idx_rows:
    _rec = ADR_DIR / _rel[2:]
    if not _rec.is_file():
        check("indexed ADR exists on disk: " + _rel, False)
        continue
    _m = re.search(r"^- \*\*Status:\*\* (\w+)", _rec.read_text(encoding="utf-8"), re.M)
    check("index status matches the record for ADR-" + _num + ": " + _shown,
          _m is not None and _m.group(1) == _shown)

for _n, _file in ((10, "0010-frontend-engineering-baseline.md"),
                  (11, "0011-required-test-categories-baseline.md"),
                  (12, "0012-principle-ix-reference-fixtures-and-no-fabricated-success.md")):
    _p = ADR_DIR / _file
    check("exists: docs/adr/" + _file, _p.is_file())
    if _p.is_file():
        _a = _p.read_text(encoding="utf-8")
        check(f"ADR-{_n:04d} names the authority it affects",
              ".claude/rules/" in _a or "00-authority.md" in _a)
    check(f"ADR-{_n:04d} is indexed", _file in _idx)

# ADR-0012 carries Status: Proposed although the decision was accepted. H5 blocks Claude from
# editing an existing record, which is the guard working as designed, so the correction is a human
# one-line edit. The inconsistency is REGISTERED rather than hidden, and this check fails the day
# the register stops saying so -- it is not an exemption.
_a12 = (ADR_DIR / "0012-principle-ix-reference-fixtures-and-no-fabricated-success.md").read_text(
    encoding="utf-8")
if re.search(r"^- \*\*Status:\*\* Proposed", _a12, re.M):
    check("the ADR-0012 status discrepancy is registered as an open item",
          "UD-10" in open_items and "0012" in open_items)

# --- MCP tooling is declared, documented, and carries no credential ---------------------------
MCP = ROOT / ".mcp.json"
check("exists: .mcp.json", MCP.is_file())
mcp_raw = MCP.read_text(encoding="utf-8")
mcp = json.loads(mcp_raw)
servers = mcp.get("mcpServers", {})
check("MCP declares serena", "serena" in servers)
check("MCP declares figma", "figma" in servers)
check("the Figma server uses the official endpoint",
      servers.get("figma", {}).get("url") == "https://mcp.figma.com/mcp")
check("no MCP credential is committed",
      not re.search(r"(api[_-]?key|token|secret|password|authorization|bearer)",
                    mcp_raw, re.I))
check("Serena project configuration is present", (ROOT / ".serena/project.yml").is_file())
check("CLAUDE.md documents both MCP servers",
      "Serena" in claude_text and "Figma" in claude_text)
check("CLAUDE.md states that MCP servers are not authority",
      "not authority" in claude_text.split("## 13. MCP tooling")[-1].lower())
check("CLAUDE.md names the local MCP verification step",
      "/mcp" in claude_text)
check("CLAUDE.md does not claim a server is connected",
      "declaring a server is not the same as having it connected" in claude_text.lower())

# --- CI/CD: the Azure DevOps definitions exist, and parity is claimed honestly ----------------
PIPELINES = ROOT / "azure-pipelines"
check("the Azure DevOps pipeline directory exists", PIPELINES.is_dir())
PARITY = PIPELINES / "PARITY.md"
PIPE_README = PIPELINES / "README.md"
check("exists: azure-pipelines/PARITY.md", PARITY.is_file())
check("exists: azure-pipelines/README.md", PIPE_README.is_file())
parity = PARITY.read_text(encoding="utf-8") if PARITY.is_file() else ""
pipe_readme = PIPE_README.read_text(encoding="utf-8") if PIPE_README.is_file() else ""

WORKFLOWS = sorted(p.name for p in (ROOT / ".github/workflows").glob("*.yml"))     if (ROOT / ".github/workflows").is_dir() else []
for _w in WORKFLOWS:
    check("workflow has an Azure DevOps counterpart on disk: " + _w,
          (PIPELINES / _w).is_file())
    check("workflow is traced in the parity matrix: " + _w, _w in parity)

for _p in sorted(PIPELINES.glob("*.yml")):
    _t = _p.read_text(encoding="utf-8")
    check("pipeline declares a pool: " + _p.name, "pool:" in _t)
    check("pipeline is named: " + _p.name, re.search(r"^name:", _t, re.M) is not None)
check("the governance guard suite has a pipeline of its own",
      (PIPELINES / "governance.yml").is_file()
      and "test_guards.py" in (PIPELINES / "governance.yml").read_text(encoding="utf-8"))
check("the pipeline README names the required build validations",
      "Which pipelines must be required" in pipe_readme)
check("the pipeline README states that optional validation is not validation",
      "Optional build validation is not build validation" in pipe_readme)
check("a pipeline is not treated as authority",
      "It is not authority" in pipe_readme or "not authority" in pipe_readme)

# .github is still present, and the parity document is honest that it must be.
check("the parity record states the criteria for deleting .github",
      "Criteria for deleting" in parity)
check("the parity record does not claim the pipelines have run",
      "They have not been run" in parity or "not met" in parity)
check("the parity record names the one partial replacement, rather than rounding it up",
      "partial by design" in parity and "UD-11" in open_items)
check("the parity record separates definition equivalence from execution",
      "definition-equivalent, not executed" in parity
      and "Not executable in current environment" in parity)
check("the parity record claims no Azure DevOps execution it cannot show",
      "executed and verified" not in parity.replace("`full — executed and verified` may be", ""))
check("the branch-protection finding is registered rather than assumed away",
      "UD-12" in open_items and "no branch protection" in parity.lower())
check("a red security gate is recorded rather than passed over",
      "UD-13" in open_items)
check("the parity record states that no gate was weakened",
      "No gate was weakened, dropped or made conditional" in parity)
check("the parity record does not claim an open gap was closed by the migration",
      "EG-6" in parity)
if "| 8 | The repository owner has the evidence above and says so | **not met** |" in parity:
    check(".github is retained while parity is unproven",
          (ROOT / ".github/workflows").is_dir())

# --- the functional record states implemented behaviour, and never a plan ---------------------
FUNCTIONAL = ROOT / "docs/functional/implemented.md"
check("exists: docs/functional/implemented.md", FUNCTIONAL.is_file())
functional = FUNCTIONAL.read_text(encoding="utf-8") if FUNCTIONAL.is_file() else ""
FORBIDDEN = ("will support", "should support", "to be implemented")
for _phrase in FORBIDDEN:
    _hits = [ln.strip()[:70] for ln in functional.splitlines()
             if _phrase in ln.lower() and "not" not in ln.lower()]
    check("functional record states no future behaviour as implemented: " + _phrase,
          not _hits)
for _label in ("Implemented", "Wired but inert", "Test-only", "Not implemented"):
    check("functional record classifies behaviour: " + _label, _label in functional)
check("90-functional-knowledge.md still forbids architecture as functional evidence",
      "never** evidence that a capability is implemented" in RULE_TEXT["90-functional-knowledge.md"])
check("90-functional-knowledge.md still requires the implement-verify-record ordering",
      "Update implemented.md" in RULE_TEXT["90-functional-knowledge.md"])

print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
for failure in FAILURES:
    print("FAILED: " + failure)
raise SystemExit(1 if FAILURES else 0)
