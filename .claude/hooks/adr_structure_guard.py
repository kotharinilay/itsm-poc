#!/usr/bin/env python3
"""H5 - ADR structure guard.

Purpose: an ADR that is added to ``docs/adr/`` is structurally well formed - numbered in sequence,
named to the convention, carrying a status field and the three MADR sections. This guard checks
**structure only**, deterministically, and never modifies a file.

What it deliberately does NOT do, because none of it is mechanical:

  * decide whether an ADR is conceptually required for some change;
  * decide whether the decision recorded is correct, wise or sufficiently reasoned;
  * decide whether a consequence is missing;
  * decide whether a person should accept the record, or mark one accepted.

A structurally valid ADR can still be the wrong decision and an unaccepted one. Satisfying this
guard is not acceptance - the requirement lives in ``.claude/rules/70-adr.md``, and the procedure in
``.claude/skills/adr-author/SKILL.md``.

Governed surface:

  docs/adr/*.md                 every record, ``README.md`` excepted (it is the index, not a record)

Checks applied to a **new** record:

  1. the filename begins with a four-digit ADR number;
  2. the rest of the filename is lower-case kebab-case, ending ``.md``;
  3. the number duplicates no existing record;
  4. the number continues the existing sequence (highest + 1);
  5. a ``Status:`` field exists;
  6. the ``Context``, ``Decision`` and ``Consequences`` sections exist;
  7. the title heading carries the record's own number.

A write to a record that already exists is reported rather than validated as new: ``0001``-``0009``
are historical records, preserved by default, and amending one is a human-directed act.

Usage:
  adr_structure_guard.py                    PreToolUse hook; reads the event on stdin
  adr_structure_guard.py --paths A B        report which of A, B are governed
  adr_structure_guard.py --check A B        validate A, B on disk; exit 1 if any violation
  adr_structure_guard.py --diff [ref]       report which changed files are governed
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guardlib import changed_files, matches, paths_from_event, project_dir  # noqa: E402

PREFIXES = ("docs/adr/",)
EXACT: tuple[str, ...] = ()
INDEX = "docs/adr/readme.md"

# ``0010-a-short-kebab-case-title.md`` - four digits, then lower-case words joined by hyphens.
FILENAME = re.compile(r"^(\d{4})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
NUMBERED = re.compile(r"^(\d{4})-")
STATUS = re.compile(r"^\s*(?:[-*]\s*)?\*{0,2}\s*status\s*\*{0,2}\s*:\s*(\S.*)$", re.I | re.M)
HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.M)
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)

REQUIRED_SECTIONS = ("context", "decision", "consequences")

REMINDER = """Structure required of a new record - .claude/rules/70-adr.md 70.5, 70.6:

  docs/adr/NNNN-<short-kebab-case-title>.md   four digits, lower case, single hyphens
  # NNNN. <title>            (or '# ADR-NNNN: <title>')
  - **Status:** Proposed     mandatory; Claude never writes 'Accepted' on a record it authored
  - **Date:** <YYYY-MM-DD>
  ## Context ...             '## Context and Problem Statement' also satisfies this
  ## Decision ...            '## Decision Outcome' also satisfies this
  ## Consequences

Name the authority the decision affects - the architecture document and section, or the
.claude/rules/ file and rule. Update docs/adr/README.md in the same change.

The record is written with status Proposed and then STOPS for explicit human acceptance
(.claude/rules/70-adr.md 70.3). Writing an ADR is not accepting it, and this guard is not
acceptance: it checks structure and nothing else."""


def is_governed(path: str) -> bool:
    """A record under docs/adr/, at the top level. The index is not a record."""
    if not matches(path, PREFIXES, EXACT):
        return False
    normalized = path.strip().strip("\"'").replace("\\", "/").lower()
    tail = normalized.split("docs/adr/", 1)[1]
    if not tail or "/" in tail or not tail.endswith(".md"):
        return False
    return not normalized.endswith(INDEX)


def adr_dir() -> Path:
    return Path(project_dir()) / "docs" / "adr"


def existing_numbers(excluding: str = "") -> dict[int, str]:
    """Every ADR number currently on disk, mapped to its filename."""
    found: dict[int, str] = {}
    directory = adr_dir()
    if not directory.is_dir():
        return found
    for entry in sorted(directory.glob("*.md")):
        if entry.name.lower() == "readme.md" or entry.name == excluding:
            continue
        match = NUMBERED.match(entry.name)
        if match:
            found[int(match.group(1))] = entry.name
    return found


def sections(text: str) -> list[str]:
    """Heading texts, stripped of emphasis and lower-cased."""
    return [h.replace("*", "").replace("`", "").strip().lower() for h in HEADING.findall(text)]


def check_filename(name: str, known: dict[int, str], is_new: bool) -> tuple[list[str], int | None]:
    """Structural checks 1-4. Returns the problems found and the number, when one could be read.

    The sequence check applies to a **new** record only. A record already on disk holds its number
    by history, and history is not renumbered to satisfy a later rule.
    """
    problems: list[str] = []
    match = FILENAME.match(name)
    if not match:
        if not NUMBERED.match(name):
            problems.append(
                f"filename '{name}' does not begin with a four-digit ADR number "
                "(expected NNNN-<short-kebab-case-title>.md)"
            )
            return problems, None
        problems.append(
            f"filename '{name}' is not NNNN-<short-kebab-case-title>.md "
            "(lower case, single hyphens, .md)"
        )
        number = int(NUMBERED.match(name).group(1))  # type: ignore[union-attr]
    else:
        number = int(match.group(1))

    if number in known:
        problems.append(
            f"ADR number {number:04d} is already taken by '{known[number]}'. "
            "A number is never reused, including a superseded one"
        )
    elif is_new:
        expected = max(known) + 1 if known else 1
        if number != expected:
            problems.append(
                f"ADR number {number:04d} does not continue the sequence; "
                f"the next number is {expected:04d}"
            )
    return problems, number


def check_content(text: str, number: int | None) -> list[str]:
    """Structural checks 5-7."""
    problems: list[str] = []

    if not STATUS.search(text):
        problems.append("no Status field (expected '- **Status:** Proposed')")

    present = sections(text)
    for required in REQUIRED_SECTIONS:
        if not any(heading.startswith(required) for heading in present):
            problems.append(f"no '{required.capitalize()}' section")

    title = TITLE.search(text)
    if not title:
        problems.append("no title heading ('# NNNN. <title>')")
    elif number is not None and f"{number:04d}" not in title.group(1):
        problems.append(
            f"the title heading '{title.group(1)}' does not carry the record's number {number:04d}"
        )
    return problems


def validate(path: str, text: str | None, is_new: bool = True) -> list[str]:
    """Every structural problem with this record. Empty means structurally valid."""
    name = Path(path.replace("\\", "/")).name
    problems, number = check_filename(name, existing_numbers(excluding=name), is_new)
    if text is not None:
        problems.extend(check_content(text, number))
    return problems


def content_for(path: str, tool_input: dict) -> str | None:
    """The record's full text, when this tool call carries it. Never reconstructed or guessed at.

    Only a whole-file write (the Write tool) states the final content. An Edit carries fragments,
    and a shell command carries none, so neither is validated from the event.
    """
    content = tool_input.get("content")
    named = tool_input.get("file_path")
    if not isinstance(content, str) or not isinstance(named, str):
        return None
    same = Path(named.replace("\\", "/")).name.lower() == Path(path.replace("\\", "/")).name.lower()
    return content if same else None


def on_disk(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(project_dir()) / path


def report(path: str, problems: list[str], existing: bool) -> str:
    lines = [f"  {path}"]
    if existing:
        lines.append(
            "    - this record already exists. docs/adr/0001-0009 are historical records: "
            "do not renumber, reword, merge or retroactively restatus them "
            "(.claude/rules/70-adr.md 70.6). A new decision that changes an old one is a NEW "
            "record that says what it supersedes. If a human directed this amendment, say so "
            "and proceed."
        )
    lines.extend(f"    - {problem}" for problem in problems)
    return "\n".join(lines)


def hook(event: dict) -> int:
    tool_input = event.get("tool_input") or {}
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    targets = [p for p in paths_from_event(event) if is_governed(p)]
    seen: set[str] = set()
    ordered = [p for p in targets if not (p in seen or seen.add(p))]
    if not ordered:
        return 0

    blocks: list[str] = []
    for path in ordered:
        existing = on_disk(path).is_file()
        text = content_for(path, tool_input)
        if text is None and existing:
            # An edit to a record already on disk: check what stands, and flag the amendment.
            text = on_disk(path).read_text(encoding="utf-8", errors="replace")
        problems = validate(path, text, is_new=not existing)
        if problems or existing or text is None:
            blocks.append(report(path, problems, existing))

    if not blocks:
        return 0  # a structurally valid new record; the governance gate is still the human's

    body = "\n".join(blocks)
    sys.stderr.write(f"H5 ADR structure guard:\n{body}\n\n{REMINDER}\n")
    return 2


def check(paths: list[str]) -> int:
    """Offline validation of records on disk. Reports; never blocks a tool call."""
    failed = False
    for path in paths:
        if not is_governed(path):
            print(f"{path}: not an ADR record; H5 does not apply")
            continue
        file = on_disk(path)
        text = file.read_text(encoding="utf-8", errors="replace") if file.is_file() else None
        problems = validate(path, text, is_new=not file.is_file())
        if problems:
            failed = True
            print(report(path, problems, existing=False))
        else:
            print(f"  {path}: structurally valid")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--paths":
        for hit in sorted({p for p in argv[1:] if is_governed(p)}):
            print(hit.replace("\\", "/"))
        return 0

    if argv and argv[0] == "--check":
        return check(argv[1:])

    if argv and argv[0] == "--diff":
        ref = argv[1] if len(argv) > 1 else None
        for hit in [p for p in changed_files(ref) if is_governed(p)]:
            print(hit)
        return 0

    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError, ValueError):
        # A guard that cannot read its input must not block work it cannot assess.
        return 0
    return hook(event) if isinstance(event, dict) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
