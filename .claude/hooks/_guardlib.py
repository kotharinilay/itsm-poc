"""Shared, deterministic plumbing for the Phase 4 governance guards (H2, H3).

These guards are **path guards**. They answer exactly one question: *does this tool call write to a
governed path?* They never inspect what a change means, never decide whether it is safe, correct or
approved, never decide whether an ADR is required, and never modify a file. Semantic judgement stays
in ``.claude/rules/`` and ``.claude/skills/``; a guard that guessed at meaning would produce false
positives, and a gate people learn to bypass is worse than no gate.

Two entry modes, both deterministic:

``hook``    Read a Claude Code PreToolUse event on stdin, match the paths the call would write, and
            exit 2 with a message on stderr when one is governed. Exit 2 blocks the call and hands
            the message back to Claude.
``--paths`` / ``--diff``
            Offline modes, used by ``test_guards.py`` and by anyone checking a working tree. They
            report; they never block.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

# Tool inputs that name a file the call will write.
_PATH_KEYS = ("file_path", "notebook_path", "path")

# Bash is covered because a migration or a graph module can be written from a shell command as
# easily as from Edit. The check stays syntactic and narrow: only a redirection target, or a path
# argument to one of these file-writing commands, counts as a write. A path merely *mentioned* -
# inside a heredoc body, in a grep pattern, in an echoed message - is not a write and triggers
# nothing. Nothing here interprets what a command means.
_WRITE_COMMANDS = frozenset(
    {"tee", "cp", "mv", "rm", "touch", "truncate", "install", "patch", "dd", "ed"}
)

_SEGMENT_SPLIT = re.compile(r"[;\n]|&&|\|\||\|")

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())


def normalize(path: str) -> str:
    """Repository-relative, forward-slashed, lower-cased. Windows and POSIX agree after this."""
    cleaned = path.strip().strip('"').strip("'").replace("\\", "/")
    root = project_dir().replace("\\", "/").rstrip("/")
    if root and cleaned.lower().startswith(root.lower() + "/"):
        cleaned = cleaned[len(root) + 1 :]
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lower()


def matches(path: str, prefixes: Sequence[str], exact: Sequence[str] = ()) -> bool:
    """True when the normalized path sits under a governed prefix or is a governed file."""
    candidate = normalize(path)
    if not candidate or "__pycache__" in candidate or candidate.endswith(".pyc"):
        return False
    if any(candidate == normalize(name) for name in exact):
        return True
    return any(candidate.startswith(normalize(prefix)) for prefix in prefixes)


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies. Their content is data being written, not a list of write targets."""
    lines = command.splitlines()
    kept: list[str] = []
    delimiter: str | None = None
    for line in lines:
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        kept.append(line)
        found = _HEREDOC.search(line)
        if found:
            delimiter = found.group(2)
    return "\n".join(kept)


def write_targets(command: str) -> list[str]:
    """Paths this shell command would write, by redirection or by a file-writing command."""
    targets: list[str] = []
    for segment in _SEGMENT_SPLIT.split(strip_heredocs(command)):
        tokens = segment.split()
        if not tokens:
            continue
        # Redirection: `> path`, `>> path`, `>path`, `>>path`.
        for index, token in enumerate(tokens):
            if token in (">", ">>") and index + 1 < len(tokens):
                targets.append(tokens[index + 1])
            elif token.startswith(">") and token.strip(">"):
                targets.append(token.lstrip(">"))
        # A file-writing command: every path-shaped argument is a candidate target.
        head = Path(tokens[0].strip('"' + "'")).name
        if head in _WRITE_COMMANDS or (head == "sed" and "-i" in tokens):
            targets.extend(token for token in tokens[1:] if not token.startswith("-"))
    cleaned = [token.strip("\"'()<>&") for token in targets]
    return [token for token in cleaned if token]


def paths_from_event(event: dict) -> list[str]:
    """Every path this tool call would write, taken literally from the tool input."""
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return []

    found: list[str] = []
    for key in _PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            found.append(value)
    for key in ("file_paths", "paths"):
        value = tool_input.get(key)
        if isinstance(value, list):
            found.extend(item for item in value if isinstance(item, str))
    for value in (tool_input.get("edits"), tool_input.get("files")):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found.extend(item[key] for key in _PATH_KEYS if isinstance(item.get(key), str))

    command = tool_input.get("command")
    if isinstance(command, str):
        found.extend(write_targets(command))

    return found


def governed(event: dict, prefixes: Sequence[str], exact: Sequence[str] = ()) -> list[str]:
    hits = [normalize(p) for p in paths_from_event(event) if matches(p, prefixes, exact)]
    return sorted(dict.fromkeys(hits))


def changed_files(ref: str | None = None) -> list[str]:
    """Working-tree, staged and untracked changes. Used by --diff only; it never blocks."""
    base = ["git", "diff", "--name-only"] + ([ref] if ref else [])
    commands = (
        base,
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    out: list[str] = []
    for command in commands:
        try:
            result = subprocess.run(
                command, cwd=project_dir(), capture_output=True, text=True, check=False
            )
        except OSError:
            continue
        out.extend(line for line in result.stdout.splitlines() if line.strip())
    return sorted(dict.fromkeys(out))


def run(
    *,
    name: str,
    prefixes: Sequence[str],
    exact: Sequence[str],
    message: str,
    argv: Sequence[str] | None = None,
) -> int:
    """Entry point shared by both guards.

    ``--paths a b c``  report which of the given paths are governed (offline, never blocks)
    ``--diff [ref]``   report which changed files are governed (offline, never blocks)
    no argument        act as a PreToolUse hook: exit 2 and explain when a governed path is written
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] == "--paths":
        for hit in sorted({normalize(p) for p in args[1:] if matches(p, prefixes, exact)}):
            print(hit)
        return 0

    if args and args[0] == "--diff":
        ref = args[1] if len(args) > 1 else None
        for hit in [p for p in changed_files(ref) if matches(p, prefixes, exact)]:
            print(hit)
        return 0

    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError, ValueError):
        # A guard that cannot read its input must not block work it cannot assess.
        return 0
    if not isinstance(event, dict):
        return 0

    hits = governed(event, prefixes, exact)
    if not hits:
        return 0

    listed = "\n".join(f"  - {hit}" for hit in hits)
    sys.stderr.write(f"{name}: governed path in this write:\n{listed}\n\n{message}\n")
    return 2
