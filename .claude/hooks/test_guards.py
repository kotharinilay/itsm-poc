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

# --- Phase 9: the engineering baseline is migrated, traced and honestly scoped ----------------
# These checks exist so a later edit cannot silently drop a baseline requirement, lose a rule's
# traceability, or quietly invent a TypeScript baseline. They validate the migration record
# against the authoritative sources; they do not judge whether a rule is correct.

BASELINE_RULES = [
    ROOT / ".claude/rules/00-authority.md",
    ROOT / ".claude/rules/10-principles.md",
    ROOT / ".claude/rules/20-dotnet.md",
    ROOT / ".claude/rules/21-python.md",
    ROOT / ".claude/rules/22-web-typescript.md",
    ROOT / ".claude/rules/40-testing.md",
    ROOT / ".claude/rules/60-architecture-gates.md",
    ROOT / ".claude/rules/80-security-ops.md",
]
for _f in BASELINE_RULES:
    check("exists: " + _f.name, _f.is_file())

for _f in BASELINE_RULES:
    text = _f.read_text(encoding="utf-8")
    prose = outside_fences(text)
    check(_f.name + " has a single H1", prose.count("\n# ") + prose.startswith("# ") == 1)
    check(_f.name + " has balanced code fences", text.count("```") % 2 == 0)

RULE_TEXT = {p.name: p.read_text(encoding="utf-8")
             for p in sorted((ROOT / ".claude/rules").glob("*.md"))}
ALL_RULES = "\n".join(RULE_TEXT.values())

# every rule file that governs one stack says so, and says which paths
check("20-dotnet.md declares its stack", "governs `.NET / C#` code only" in RULE_TEXT["20-dotnet.md"])
check("20-dotnet.md names its paths", "`dotnet/**`" in RULE_TEXT["20-dotnet.md"])
check("21-python.md declares its stack", "governs Python code only" in RULE_TEXT["21-python.md"])
check("21-python.md names its paths", "`ragcore/**`" in RULE_TEXT["21-python.md"]
      and "`integrations/**`" in RULE_TEXT["21-python.md"])
check("22-web-typescript.md names its paths", "`apps/web/**`" in RULE_TEXT["22-web-typescript.md"]
      and "`apps/desktop/**`" in RULE_TEXT["22-web-typescript.md"])
check(
    "no language rule silently claims another stack",
    "language-independent" not in RULE_TEXT["20-dotnet.md"].split("## 20.1")[0],
)

# --- the migration record exists and is complete ----------------------------------------------
COVERAGE = ROOT / "docs/migration/phase-9-baseline-coverage.md"
check("exists: phase-9-baseline-coverage.md", COVERAGE.is_file())
coverage_text = COVERAGE.read_text(encoding="utf-8") if COVERAGE.is_file() else ""
for _heading in (
    "## 1. Inputs",
    "## 2. Inventory",
    "## 3. Applicability matrix",
    "## 4. Semantic preservation",
    "## 5. Enforcement",
    "## 6. Traceability",
    "## 7. Dropped-rule recovery",
    "## 8. Deviations",
    "## 9. Unresolved decisions",
):
    check("coverage record has " + _heading, _heading in coverage_text)

BASELINE_INPUT = ROOT / "docs/migration/phase-9-baseline-input.md"
check("exists: phase-9-baseline-input.md", BASELINE_INPUT.is_file())

# --- traceability: every authoritative baseline id reaches both the record and a rule ----------
YAML_PACKS = ["principles.yaml", "dotnet.yaml", "dotnet_lang.yaml",
              "python.yaml", "python_lang.yaml"]
for _pack in YAML_PACKS:
    check("baseline pack present: " + _pack, (ROOT / _pack).is_file())


def keyed_ids(pack: str) -> list[str]:
    """The explicit `id:` values in a rule pack, qualified the way the matrices identify them."""
    raw = re.findall(r"^\s*-?\s*id:\s*(\S+)\s*$",
                     (ROOT / pack).read_text(encoding="utf-8"), re.M)
    out = []
    for rid in raw:
        if rid.startswith("P-DN"):
            out.append("dotnet.yaml#" + rid)
        elif rid.startswith("P-PY"):
            out.append("python.yaml#" + rid)
        else:
            out.append(rid)
    return out


KEYED = {pack: keyed_ids(pack) for pack in YAML_PACKS}
KEYED_TOTAL = sum(len(v) for v in KEYED.values())
check("the packs still carry exactly 115 keyed rule ids", KEYED_TOTAL == 115)
for _pack, _expected in [("principles.yaml", 32), ("dotnet.yaml", 12), ("dotnet_lang.yaml", 37),
                         ("python.yaml", 9), ("python_lang.yaml", 25)]:
    check(f"{_pack} keyed id count is {_expected}", len(KEYED[_pack]) == _expected)

# the 13 requirements that carry no `id:` in the source and were promoted into matrix rows
UNKEYED_IDS = [
    "dotnet.yaml#baseline", "python.yaml#baseline",
    "dotnet.yaml#toolchain.analyzers", "dotnet.yaml#toolchain.formatter",
    "dotnet.yaml#toolchain.style_in_build", "dotnet.yaml#toolchain.warnings",
    "dotnet.yaml#toolchain.packages",
    "python.yaml#toolchain.linter", "python.yaml#toolchain.formatter",
    "python.yaml#toolchain.import_sort", "python.yaml#toolchain.type_checker",
    "python.yaml#toolchain.security", "python.yaml#toolchain.packaging",
]
check("13 unkeyed baseline requirements are enumerated", len(UNKEYED_IDS) == 13)
check("115 keyed + 13 unkeyed reproduce the Phase 2 total of 128",
      KEYED_TOTAL + len(UNKEYED_IDS) == 128)

# the explicit baseline block: 39 items, Phase 9 migration ids BL-01..BL-39
BL_IDS = [f"BL-{i:02d}" for i in range(1, 40)]
if BASELINE_INPUT.is_file():
    check(
        "the baseline block still holds 39 items",
        len(re.findall(r"^\\- ", BASELINE_INPUT.read_text(encoding="utf-8"), re.M)) == 39,
    )

ALL_BASELINE_IDS = [i for v in KEYED.values() for i in v] + UNKEYED_IDS + BL_IDS
check("167 baseline requirements are accounted for", len(ALL_BASELINE_IDS) == 167)

_missing_record = [r for r in ALL_BASELINE_IDS if r not in coverage_text]
check("every baseline id appears in the migration record: "
      + (", ".join(_missing_record[:5]) or "all present"), not _missing_record)

_missing_rule = [r for r in ALL_BASELINE_IDS if r not in ALL_RULES]
check("every baseline id is traceable from a rule file: "
      + (", ".join(_missing_rule[:5]) or "all present"), not _missing_rule)

# Phase 9 ids are assigned in the record, never written back into an authoritative source
_leaked = [p for p in YAML_PACKS
           if re.search(r"\bBL-\d\d\b", (ROOT / p).read_text(encoding="utf-8"))]
check("no Phase 9 BL id was written into a source pack: " + (", ".join(_leaked) or "clean"),
      not _leaked)

# --- the applicability matrix is complete, unique, and its roll-up has not drifted ------------
_LABELS = ("mechanical", "partial", "procedural", "currently-unenforced", "not-applicable")
_matrix_ids: list[str] = []
_enf_counts: dict[str, int] = {lbl: 0 for lbl in _LABELS}
for _line in coverage_text.splitlines():
    if not _line.startswith("| "):
        continue
    _cells = [c.strip() for c in re.split(r"(?<!\\)\|", _line.strip("|"))]
    if len(_cells) != 8 or _cells[4] not in _LABELS:
        continue
    _matrix_ids.append(_cells[0])
    _enf_counts[_cells[4]] += 1

check("the applicability matrix holds one row per requirement", len(_matrix_ids) == 167)
check("no requirement is represented twice in the matrix",
      len(set(_matrix_ids)) == len(_matrix_ids))
check("every matrix row carries an enforcement label",
      sum(_enf_counts.values()) == len(_matrix_ids))
for _lbl in _LABELS:
    check(
        f"the enforcement roll-up matches the matrix for {_lbl}",
        f"| `{_lbl}` | {_enf_counts[_lbl]} |" in coverage_text,
    )

# --- the rules Phase 7 found dropped are present as requirements, not only as gates -----------
DROPPED = {
    "Conventional Commits": "### C-1 — Conventional Commits",
    "SemVer": "### C-2 — Semantic Versioning",
    "Diataxis": "### C-3 — Documentation structure: Diátaxis",
    "C4": "### C-4 — Architecture diagrams: C4",
    "README quickstart + ADR pointer": "### C-5 — README: quickstart and ADR pointer",
}
for _label, _needle in DROPPED.items():
    holders = [n for n, t in RULE_TEXT.items() if _needle in t]
    check("recovered dropped rule is stated exactly once: " + _label, len(holders) == 1)

check("Conventional Commits states the actual grammar",
      "BREAKING CHANGE:" in RULE_TEXT["10-principles.md"]
      and "refactor" in RULE_TEXT["10-principles.md"])
check("SemVer states the actual bump rule",
      "MAJOR.MINOR.PATCH" in RULE_TEXT["10-principles.md"])
check("Diataxis names its four kinds",
      all(k in RULE_TEXT["10-principles.md"]
          for k in ("Tutorial", "How-to guide", "Reference", "Explanation")))
check("C4 names its levels",
      "System Context" in RULE_TEXT["10-principles.md"]
      and "Container" in RULE_TEXT["10-principles.md"])

# both source ids survive the consolidation of the duplicated profile conventions
for _pair in ("dotnet.yaml#P-DN-4", "python.yaml#P-PY-4",
              "dotnet.yaml#P-DN-6", "python.yaml#P-PY-6"):
    check("consolidated convention keeps its source id: " + _pair,
          _pair in RULE_TEXT["10-principles.md"])

# --- the repository-wide principle stays repository-wide --------------------------------------
check("P17 least privilege is repository-wide, not DB-only",
      "P-17 — Least privilege (repository-wide)" in RULE_TEXT["10-principles.md"])
check("P17's operational surfaces are enumerated",
      "principles#P17" in RULE_TEXT["80-security-ops.md"])

# --- the engineering requirement survives alongside its governance gate ------------------------
check("DN21 states the suppression requirement itself",
      "scoped and carries a justification" in RULE_TEXT["20-dotnet.md"]
      or "scoped and justified" in RULE_TEXT["20-dotnet.md"])
check("DN21 is not represented only as an ADR trigger",
      "#pragma warning restore" in RULE_TEXT["20-dotnet.md"])

# --- no TypeScript baseline was invented -------------------------------------------------------
check("the TS/Angular/Electron gap is recorded verbatim",
      "TYPESCRIPT/ANGULAR/ELECTRON-SPECIFIC BASELINE NOT DEFINED"
      in RULE_TEXT["22-web-typescript.md"])
check("existing TS tooling is not promoted to baseline authority",
      "NOT BASELINE AUTHORITY" in RULE_TEXT["22-web-typescript.md"])
check("the TS decision is named as a human decision",
      "HUMAN DECISION REQUIRED" in RULE_TEXT["22-web-typescript.md"])

# --- enforcement claims are stated with the honest vocabulary ---------------------------------
for _needle in ("mechanical", "partial", "procedural", "currently-unenforced"):
    check("coverage record uses the enforcement label " + _needle, _needle in coverage_text)
for _rule, _file in (("lang/dotnet#DN8", "20-dotnet.md"), ("lang/dotnet#DN31", "20-dotnet.md"),
                     ("lang/python#PY4", "21-python.md")):
    check(_rule + " is recorded as unenforced, not claimed green",
          "currently-unenforced" in RULE_TEXT[_file])
check("the re-verified Phase 7 enforcement errors are all recorded",
      all(r in coverage_text for r in
          ("lang/dotnet#DN8", "lang/dotnet#DN31", "lang/dotnet#DN16", "lang/python#PY4")))

# --- conflicts are recorded, not reconciled ----------------------------------------------------
check("the EF-migrations conflict is recorded", "CF-1" in coverage_text)
check("the conflict names both sources",
      "BL-10" in RULE_TEXT["20-dotnet.md"] and "50-database.md" in RULE_TEXT["20-dotnet.md"])
check("the migration invariant is not weakened by the conflict",
      "NoMigrationTests" in RULE_TEXT["20-dotnet.md"])
check("deviations are recorded rather than repaired", "DV-1" in coverage_text)
check("enforcement gaps are recorded rather than closed", "EG-1" in coverage_text)

# --- root CLAUDE.md -----------------------------------------------------------------------------
CLAUDE_MD = ROOT / "CLAUDE.md"
check("exists: CLAUDE.md", CLAUDE_MD.is_file())
claude_text = CLAUDE_MD.read_text(encoding="utf-8") if CLAUDE_MD.is_file() else ""
check("CLAUDE.md is concise", 0 < len(claude_text.splitlines()) <= 200)
for _doc in ("identity-plane-final.md", "Synthia-OverallArchitecture-final.md",
             "RagAgent-Architecture-final.md"):
    check("CLAUDE.md names architecture authority " + _doc, _doc in claude_text)
for _gate in ("50-database.md", "30-langgraph.md", "70-adr.md", "90-functional-knowledge.md"):
    check("CLAUDE.md names the gate " + _gate, _gate in claude_text)
check("CLAUDE.md names docs/functional/implemented.md",
      "docs/functional/implemented.md" in claude_text)
check("CLAUDE.md names the baseline sources",
      "principles.yaml" in claude_text and "phase-9-baseline-input.md" in claude_text)
check("CLAUDE.md says Spec Kit artifacts are not authoritative",
      "not authoritative" in claude_text.lower())
check("CLAUDE.md distinguishes rules from skills",
      ".claude/rules/" in claude_text and ".claude/skills/" in claude_text)
check("CLAUDE.md does not inline the baseline", "principles#P1" not in claude_text)
_listed = [n for n in RULE_TEXT if n in claude_text]
check("CLAUDE.md indexes every rule file", len(_listed) == len(RULE_TEXT))

# --- every .claude path referenced by a rule or by CLAUDE.md actually exists --------------------
_refs = set()
for _text in list(RULE_TEXT.values()) + [claude_text]:
    for _m in re.finditer(r"`(\.claude/[A-Za-z0-9_./-]+)`", _text):
        _refs.add(_m.group(1))
_broken = sorted(r for r in _refs
                 if "*" not in r and "<" not in r and not (ROOT / r).exists())
check("every .claude path referenced by the rules exists: "
      + (", ".join(_broken[:5]) or "all resolve"), not _broken)

# --- the pre-existing governance rules were not rewritten to fit the baseline ------------------
for _name, _needle in (("30-langgraph.md", "execution_treatment"),
                       ("50-database.md", "identity-bearing"),
                       ("70-adr.md", "MADR"),
                       ("90-functional-knowledge.md", "implemented.md")):
    check("pre-existing governance intact: " + _name, _needle in RULE_TEXT[_name])

print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
for failure in FAILURES:
    print("FAILED: " + failure)
raise SystemExit(1 if FAILURES else 0)
