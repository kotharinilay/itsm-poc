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
    """The root Claude Code advertises. Kept for compatibility; it is a *hint*, not the answer.

    In a Git worktree this names the primary checkout while the tool call writes under the worktree
    root, which is why it can never be the only root a path is normalized against.
    """
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())


def _slashed(path: str) -> str:
    return str(path).replace("\\", "/").rstrip("/")


def _is_absolute(path: str) -> bool:
    """POSIX root, UNC share, or a Windows drive. Decided on the string, not on this platform."""
    return path.startswith("/") or bool(re.match(r"^[A-Za-z]:/", path))


def _collapse(path: str) -> str:
    """Normalize '.' and '..' on a forward-slashed path without touching the filesystem."""
    drive = re.match(r"^([A-Za-z]:)/", path)
    if drive:
        lead, rest = drive.group(1) + "/", path[len(drive.group(1)) + 1 :]
    elif path.startswith("//"):
        lead, rest = "//", path[2:]
    elif path.startswith("/"):
        lead, rest = "/", path[1:]
    else:
        lead, rest = "", path
    parts: list[str] = []
    for part in rest.split("/"):
        if part in ("", "."):
            continue
        if part == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(part)
    return lead + "/".join(parts)


# Discovery answers are stable for the life of a hook process; each directory is asked once.
_ROOT_CACHE: dict[str, tuple[str, str]] = {}
_GIT_CACHE: dict[tuple[str, str], str] = {}


def reset_root_cache() -> None:
    """Forget the cached answers. Used by the tests, which move between real worktrees."""
    _ROOT_CACHE.clear()
    _GIT_CACHE.clear()


def _primary_behind(root: str) -> str:
    """The primary checkout behind a linked worktree, read from its ``.git`` file.

    A linked worktree's ``.git`` is a file holding ``gitdir: <primary>/.git/worktrees/<name>``.
    The primary checkout is therefore the parent of that ``.git`` directory. A normal checkout has
    a ``.git`` directory and is its own primary, so this returns nothing for it.
    """
    marker = Path(root) / ".git"
    try:
        if not marker.is_file():
            return ""
        pointer = marker.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not pointer.lower().startswith("gitdir:"):
        return ""
    gitdir = _slashed(pointer.split(":", 1)[1].strip())
    marker_dir = "/.git/worktrees/"
    index = gitdir.lower().find(marker_dir)
    if index == -1:
        return ""
    return _collapse(gitdir[:index])


def _discover(start_dir: str) -> tuple[str, str]:
    """(worktree root, primary checkout root) for ``start_dir``, or ('', '').

    Discovery is the repository's own: ascend until a ``.git`` entry appears. That entry marks the
    worktree root whether it is a directory (normal checkout) or a file (linked worktree), which is
    exactly the distinction that was being missed. It reads the filesystem and spawns nothing, so
    it is cheap enough to run on every PreToolUse event.
    """
    if not start_dir:
        return ("", "")
    key = start_dir.lower()
    if key in _ROOT_CACHE:
        return _ROOT_CACHE[key]

    answer = ("", "")
    candidate = Path(start_dir)
    for _ in range(64):
        try:
            if (candidate / ".git").exists():
                root = _collapse(_slashed(str(candidate)))
                answer = (root, _primary_behind(root) or root)
                break
        except OSError:
            break
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    else:
        answer = ("", "")

    if answer == ("", ""):
        # Nothing on disk said so. Ask Git directly before giving up: a repository reached through
        # GIT_DIR, or any layout this walk does not model, still answers here.
        top = _git("top", start_dir)
        if top:
            answer = (top, _git("common", start_dir) or top)

    _ROOT_CACHE[key] = answer
    return answer


def _git(kind: str, start: str) -> str:
    """Fallback discovery: the worktree root ('top') or the primary checkout root ('common')."""
    key = (kind, start.lower())
    if key in _GIT_CACHE:
        return _GIT_CACHE[key]
    command = (
        ["git", "-C", start, "rev-parse", "--show-toplevel"]
        if kind == "top"
        else ["git", "-C", start, "rev-parse", "--path-format=absolute", "--git-common-dir"]
    )
    answer = ""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=15)
        if result.returncode == 0:
            answer = _collapse(_slashed(result.stdout.strip()))
            if kind == "common" and answer:
                # <primary checkout>/.git -> <primary checkout>
                answer = _collapse(_slashed(str(Path(answer).parent)))
    except (OSError, subprocess.SubprocessError):
        answer = ""
    _GIT_CACHE[key] = answer
    return answer


def _nearest_existing_dir(path: str) -> str:
    """The closest ancestor of ``path`` that exists, so it can be asked about."""
    candidate = Path(path)
    for _ in range(64):
        try:
            if candidate.is_dir():
                return _slashed(str(candidate))
        except OSError:
            return ""
        parent = candidate.parent
        if parent == candidate:
            return ""
        candidate = parent
    return ""


def repo_roots(hint_dir: str = "") -> list[str]:
    """Every root a governed path may legitimately be expressed against, longest first.

    Discovery order, none of it hard-coded to this repository:

      * the Git worktree root containing the path being normalized - the reliable source, and the
        one that makes a worktree behave exactly like the primary checkout;
      * the Git worktree root containing the current working directory;
      * the primary checkout behind either of those (``--git-common-dir``), so a path written
        against the main checkout still normalizes while Claude works from a worktree;
      * ``CLAUDE_PROJECT_DIR``, the working directory, and the checkout this hook file itself lives
        in - fallbacks for when Git is unavailable or the tree is not a repository.

    Longest first, because a worktree placed under the primary checkout (``.claude/worktrees/x``)
    shares its prefix and the longer root is the correct one.
    """
    cwd = _slashed(str(Path.cwd()))
    found: list[str] = []
    for start in (hint_dir, cwd):
        if start:
            found.extend(_discover(start))
    found.append(_slashed(os.environ.get("CLAUDE_PROJECT_DIR") or ""))
    # This file is <root>/.claude/hooks/_guardlib.py.
    found.append(_slashed(str(Path(__file__).resolve().parents[2])))

    unique: dict[str, None] = {}
    for root in found:
        if root:
            unique.setdefault(_collapse(root), None)
    if not unique:
        # Nothing identified a repository. Only now is the working directory treated as the root:
        # taken earlier it would be the longest match whenever a hook runs from a subdirectory,
        # and it would strip away the very path segments the governed prefixes are written in.
        unique.setdefault(_collapse(cwd), None)
    return sorted(unique, key=len, reverse=True)


def _strip_root(absolute: str) -> str:
    """The repository-relative remainder of an absolute path, or '' when no root contains it."""
    lowered = absolute.lower()
    for root in repo_roots(_nearest_existing_dir(absolute)):
        if lowered.startswith(root.lower() + "/"):
            return absolute[len(root) + 1 :]
    return ""


def _absolute_form(cleaned: str) -> str:
    """``cleaned`` as an absolute path: itself, or resolved against the working directory."""
    if _is_absolute(cleaned):
        return _collapse(cleaned)
    return _collapse(_slashed(str(Path.cwd())) + "/" + cleaned)


def _literal(path: str) -> str:
    """Cleaned, forward-slashed, lower-cased - and nothing else.

    The governed prefixes are authored repository-relative, so they are never resolved against a
    working directory. Doing so would corrupt them whenever a hook runs from a subdirectory.
    """
    cleaned = path.strip().strip('"').strip("'").replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lower()


def normalize(path: str) -> str:
    """Repository-relative, forward-slashed, lower-cased. The canonical form, used for reporting.

    The same governed file normalizes identically however it is named: relative or absolute, from
    the primary checkout or from a Git worktree, with ``CLAUDE_PROJECT_DIR`` set or absent.
    """
    forms = normalize_candidates(path)
    return forms[0] if forms else ""


def normalize_candidates(path: str) -> list[str]:
    """Every repository-relative form this path could legitimately denote, best first.

    An absolute path has exactly one: the remainder under the root that contains it. A relative one
    has up to two - resolved against the working directory (correct when the hook runs from a
    subdirectory or a worktree) and taken literally (correct when it was already written
    repository-relative). A guard tests both, because missing a governed write is the failure that
    matters; naming one path two ways costs nothing.
    """
    raw = path.strip().strip('"').strip("'").replace("\\", "/")
    cleaned = raw.rstrip("/")
    if not cleaned:
        return []
    trailing = "/" if raw.endswith("/") else ""

    if _is_absolute(cleaned):
        absolute = _collapse(cleaned)
        return [((_strip_root(absolute) or absolute) + trailing).lower()]

    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    forms = [(_strip_root(_absolute_form(cleaned)) + trailing).lower(), (cleaned + trailing).lower()]
    unique: dict[str, None] = {}
    for form in forms:
        if form.strip("/"):
            unique.setdefault(form, None)
    return list(unique)


def root_for(path: str) -> str:
    """The repository root this path belongs to - the worktree's when it names one."""
    absolute = _absolute_form(_slashed(path.strip().strip('"').strip("'")))
    lowered = absolute.lower()
    for root in repo_roots(_nearest_existing_dir(absolute)):
        if lowered.startswith(root.lower() + "/"):
            return root
    return active_root()


def active_root() -> str:
    """The root Claude is actually working in: the current worktree, else the advertised project."""
    cwd = _slashed(str(Path.cwd()))
    return _discover(cwd)[0] or _collapse(_slashed(project_dir())) or cwd


def resolve_in_repo(path: str) -> Path:
    """An absolute filesystem path for ``path``, resolved against the root that governs it."""
    cleaned = _slashed(path.strip().strip('"').strip("'"))
    if _is_absolute(cleaned):
        return Path(_collapse(cleaned))
    return Path(_collapse(root_for(path) + "/" + cleaned))


def matches(path: str, prefixes: Sequence[str], exact: Sequence[str] = ()) -> bool:
    """True when the path, in any form it could legitimately denote, is a governed file."""
    governed_exact = [_literal(name) for name in exact]
    governed_prefixes = [_literal(prefix) for prefix in prefixes]
    for candidate in normalize_candidates(path):
        if not candidate or "__pycache__" in candidate or candidate.endswith(".pyc"):
            continue
        if candidate in governed_exact:
            return True
        if any(candidate.startswith(prefix) for prefix in governed_prefixes):
            return True
    return False


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
                command, cwd=active_root(), capture_output=True, text=True, check=False
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
