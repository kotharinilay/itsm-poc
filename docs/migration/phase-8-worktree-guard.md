# Phase 8 — Worktree-aware governance enforcement

**Status of this document.** It is a remediation record for a single enforcement defect. It changed
no application source, schema, migration, graph topology or state, ADR, architecture document,
contract, CI definition or Spec Kit asset. It changed no governance *policy*: what counts as a
database change, a LangGraph change or an ADR structural violation is exactly what it was, and the
stop/approval behaviour of H2, H3 and H5 is unchanged. Only the path on which those unchanged
policies are enforced was repaired.

Baseline revision audited and repaired: `0faf2c05fdfeaa9ec28a536ee13ba8361226756d`.

---

## 1. Problem reproduced

Phase 7 blocker **B-3** reported that the governance hooks do not fire inside a Git worktree. It was
reproduced here before anything was changed, against a **real** worktree created with
`git worktree add --detach`, by feeding each guard a genuine `PreToolUse` event on stdin and reading
its exit code (`2` blocks the call, `0` allows it).

| # | Working directory | Path form in `tool_input.file_path` | `CLAUDE_PROJECT_DIR` | H2 | H3 | H5 |
|---|---|---|---|---|---|---|
| A | primary checkout | absolute, under the primary checkout | primary checkout | `2` | `2` | `2` |
| **B** | **Git worktree** | **absolute, under the worktree** | **primary checkout** | **`0`** | **`0`** | **`0`** |
| C | Git worktree | relative | primary checkout | `2` | `2` | `2` |
| D | Git worktree | absolute, under the worktree | *unset* | `2` | `2` | `2` |

Row **B** is the bypass: a write to `ragcore/migrations/versions/…`,
`ragcore/src/ragcore/graph/…` or `docs/adr/…` made from a worktree was **not detected by any of the
three guards**, and the tool call proceeded with no gate.

Row D passed only incidentally — with `CLAUDE_PROJECT_DIR` unset, `project_dir()` falls back to the
working directory, which in that row happened to be the worktree root. The protection was accidental,
not designed.

A second form of the same defect was reproduced directly against `_guardlib.normalize()`, and it is
the more dangerous one because it is the layout `EnterWorktree` uses by default:

```text
input : D:/Projects/synthia/.claude/worktrees/feat/ragcore/migrations/0026_x.py
output: .claude/worktrees/feat/ragcore/migrations/0026_x.py      <- matches no governed prefix
input : C:/tmp/wt/ragcore/migrations/0026_x.py
output: c:/tmp/wt/ragcore/migrations/0026_x.py                   <- matches no governed prefix
```

## 2. Root cause

`.claude/hooks/_guardlib.py::normalize()` reduced a path to repository-relative form by stripping
**exactly one** candidate root:

```python
def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())

def normalize(path: str) -> str:
    ...
    root = project_dir().replace("\\", "/").rstrip("/")
    if root and cleaned.lower().startswith(root.lower() + "/"):
        cleaned = cleaned[len(root) + 1 :]
```

Claude Code sets `CLAUDE_PROJECT_DIR` to the **primary checkout**, while a tool call made from a
worktree names a file under the **worktree root**. Two failure shapes follow:

1. **Disjoint roots** (worktree outside the primary checkout). The primary-checkout prefix does not
   match at all, nothing is stripped, and an absolute path can never match a repository-relative
   governed prefix such as `ragcore/migrations/`.
2. **Nested roots** (`.claude/worktrees/<name>/`, the `EnterWorktree` layout). The primary-checkout
   prefix *does* match, but it is the **shorter, wrong** root: stripping it leaves
   `.claude/worktrees/<name>/ragcore/migrations/…`, which again matches no governed prefix.

The guards' governed-path tables were never wrong. The defect was entirely in reducing a path to the
form those tables are written in.

`.claude/hooks/adr_structure_guard.py` carried the same assumption twice more, in
`adr_dir()` and `on_disk()`: both resolved against `project_dir()`, so from a worktree H5 read the
**primary checkout's** `docs/adr/` when deciding the next ADR number and when reading a record.

Two further defects were found while building the fix, both by tests written for this phase rather
than by inspection. They are recorded here because they were live in the repaired code at the time,
not in the original:

- Resolving a relative path against the working directory is correct, but resolving the **governed
  prefixes** the same way is not — they are authored repository-relative and must stay literal.
  Otherwise a hook running from a subdirectory corrupts both sides of the comparison.
- Treating the working directory as a candidate root unconditionally makes it the *longest* match
  whenever a hook runs from a subdirectory, stripping away the very leading segments the governed
  prefixes are written in.

## 3. Detection / normalization strategy

Root discovery is now derived **from the repository**, not from an environment variable.

`_discover(start_dir)` ascends from a directory until it finds a `.git` entry. That entry marks the
worktree root whether it is a **directory** (a normal checkout) or a **file** (a linked worktree) —
precisely the distinction that was being missed. When the marker is a file it holds
`gitdir: <primary>/.git/worktrees/<name>`, from which the primary checkout is read directly. The walk
touches only the filesystem and spawns no process, which matters because this runs on every
`PreToolUse` event. If the walk finds nothing — a repository reached through `GIT_DIR`, or any layout
the walk does not model — `git rev-parse --show-toplevel` and
`git rev-parse --path-format=absolute --git-common-dir` are consulted as a fallback. Both discovery
results are cached per directory for the life of the process.

`repo_roots(hint_dir)` returns every root a governed path may legitimately be expressed against,
**longest first**:

1. the worktree root and primary checkout containing **the path being normalized** (the reliable
   source, and the one that makes a worktree behave exactly like the primary checkout);
2. the worktree root and primary checkout containing the **working directory**;
3. `CLAUDE_PROJECT_DIR`, and the checkout this hook file itself lives in;
4. the working directory — **only if none of the above identified a repository**.

Longest-first is what makes the nested `.claude/worktrees/<name>/` layout resolve correctly: the
worktree root and the primary checkout share a prefix, and the longer one is the right answer.

`normalize_candidates(path)` returns every repository-relative form a path could legitimately denote:

- an **absolute** path has one — the remainder under the longest root containing it;
- a **relative** path has up to two — resolved against the working directory (correct from a
  subdirectory or a worktree) and taken literally (correct when it was already written
  repository-relative).

`matches()` compares every candidate against the governed tables, and the governed prefixes are
normalized by `_literal()` — cleaned and lower-cased only, never resolved. A path is governed if
**any** of its forms is governed. This is deliberately inclusive: naming one file two ways costs
nothing, and missing a governed write is the failure that matters. It is strictly more protective
than the behaviour it replaces, never less.

`normalize()` remains the canonical single form used for reporting. `root_for()`, `active_root()` and
`resolve_in_repo()` expose the same discovery to the guards, and H5 now uses them so that the ADR
number sequence and the record on disk are read from **the root in use**. `changed_files()` (`--diff`)
runs against the active root for the same reason.

No local filesystem path is hard-coded; a test asserts this.

## 4. Files changed

| File | Change |
|---|---|
| `.claude/hooks/_guardlib.py` | Worktree-aware root discovery (`_discover`, `_primary_behind`, `repo_roots`, `_strip_root`), `normalize_candidates`, literal prefix handling in `matches`, and the `root_for` / `active_root` / `resolve_in_repo` / `reset_root_cache` helpers. `changed_files()` now runs against the active root. |
| `.claude/hooks/adr_structure_guard.py` | `adr_dir()`, `existing_numbers()` and `on_disk()` resolve against the root that governs the record instead of `project_dir()`; `is_governed()` decides on the normalized forms rather than on the literal string. No check, threshold or message changed. |
| `.claude/hooks/test_guards.py` | New real-Git-worktree regression section: the matrix, the subdirectory cases, the end-to-end hook contract from a worktree, and the plant/restore evidence. No existing check was deleted, skipped, loosened or narrowed. |
| `docs/migration/phase-8-worktree-guard.md` | This record. |

`.claude/hooks/db_migration_guard.py` and `.claude/hooks/langgraph_change_guard.py` were **not
changed**: both are thin declarations over `_guardlib.run`, and repairing the library repaired them.

## 5. Regression matrix

Every combination below is asserted for **H2, H3 and H5**, for a governed path (must be detected) and
for a non-governed path (must not be), through the guards' own entry points.

| Root | Path form | `CLAUDE_PROJECT_DIR` |
|---|---|---|
| primary checkout | relative · absolute | set · absent |
| external Git worktree (temporary directory, disjoint from the primary checkout) | relative · absolute | set · absent |
| nested Git worktree (`.claude/worktrees/<name>`, the `EnterWorktree` layout) | relative · absolute | set · absent |

Both worktrees are created by `git worktree add --detach` during the run and are asserted to be
**linked worktrees** (`.git` is a file, not a directory) before anything is concluded from them. No
worktree is simulated by string manipulation.

A second matrix covers the working directory being a **subdirectory** of the tree — a `Bash` tool call
can change directory, so a hook does not always run from the root. For each root above and each
guard, with `CLAUDE_PROJECT_DIR` set and absent, a governed path is asserted detected when written
subdirectory-relative, repository-relative, and absolute.

The end-to-end hook contract is then exercised as a subprocess, invoking the **primary checkout's**
guard script exactly as `.claude/settings.json` does, with the working directory set to a worktree,
an absolute path under that worktree, and `CLAUDE_PROJECT_DIR` still naming the primary checkout —
the exact Phase 7 bypass. Exit `2` and a non-empty explanation on stderr are both asserted; a
non-governed write from the same position is asserted to exit `0`.

Temporary worktrees are removed in a `finally` block, a stale probe from an interrupted run is
cleared before a new one is created, and removal retries briefly because a just-read checkout can
hold transient handles on Windows. Three consecutive suite runs were clean.

## 6. Mutation / plant evidence

### Planted violations

Real files are written into a real worktree, each guard's `--diff` is run from that worktree, the
files are removed, and `--diff` is run again.

| Planted file | Guard | Before planting | Planted | After removal |
|---|---|---|---|---|
| `ragcore/migrations/versions/0026_planted_violation.py` | H2 | not reported | **reported** | not reported |
| `ragcore/src/ragcore/graph/planted_violation.py` | H3 | not reported | **reported** | not reported |
| `docs/adr/9999-planted-violation.md` | H5 | not reported | **reported** | not reported |

The planted ADR is additionally validated with `adr_structure_guard.py --check` **from the worktree**:
it exits `1` and names the missing status, context, decision and consequences. Before the fix this
path read the primary checkout's `docs/adr/`.

### Mutation testing of the fix

Each mutation was applied to the repaired `_guardlib.py` in isolation, on a clean tree, and the full
suite was run. All three are caught; the implementation was restored after each.

| Mutation | Result |
|---|---|
| **M1** — root discovery collapses to `CLAUDE_PROJECT_DIR` only (the Phase 7 behaviour) | **48 checks fail** (318/366) |
| **M2** — governed prefixes resolved against the working directory instead of taken literally | **36 checks fail** (330/366) |
| **M3** — a linked worktree's `.git` **file** no longer recognised as a root marker | **24 checks fail** (342/366) |

M3 fails entirely on the **nested** worktree, which is the honest result: for a worktree outside the
primary checkout the `git rev-parse` fallback still finds the root, whereas in the nested layout the
walk stops at the primary checkout's `.git` directory and the wrong root wins. The nested layout is
the one `EnterWorktree` uses.

## 7. Test results

| Command | Before | After |
|---|---|---|
| `python3 .claude/hooks/test_guards.py` | `188/188 checks passed` | `366/366 checks passed` |

178 checks were added; **none** was deleted, skipped, `xfail`ed, loosened or narrowed. Runtime is
about 35 seconds, dominated by interpreter startup (measured at ~2.4 s per process on this machine)
and by `git worktree add` checking out 833 files twice.

`.claude/settings.json` defines no validation command; it wires the three `PreToolUse` guards, and the
suite asserts that each is wired exactly once, that the matcher covers the file-writing tools, and
that no developer-local override exists. Those checks pass.

Working-tree check after the repair, from the primary checkout:

```text
python3 .claude/hooks/db_migration_guard.py --diff      -> no governed paths, exit 0
python3 .claude/hooks/langgraph_change_guard.py --diff  -> no governed paths, exit 0
python3 .claude/hooks/adr_structure_guard.py --diff     -> no governed paths, exit 0
```

No pre-existing test failed. No test was weakened.

## 8. Remaining limitations

1. **The guards remain path guards.** They answer "does this tool call write to a governed path?" and
   nothing else. Satisfying one is still not approval, and the repair does not make any guard
   semantic. Rules 30, 50 and 70 remain the requirement.
2. **A path the tool input does not name is still not seen.** Coverage of `Bash` is syntactic and
   narrow by design — redirections and a fixed set of file-writing commands. A write performed by,
   for example, a Python script invoked from `Bash` is outside every guard, before and after this
   change. Unchanged by this phase, and recorded rather than fixed.
3. **`git rev-parse` fallback assumes `git` is on `PATH`.** When it is not and the `.git` marker walk
   also fails, discovery falls back to `CLAUDE_PROJECT_DIR`, the hook file's own checkout, and
   finally the working directory — i.e. to the pre-Phase-8 behaviour for that call. The fallback is
   strictly a superset of what existed before.
4. **A submodule root is treated as its own root.** A `.git` file inside a submodule marks the
   submodule as the root, so a path inside one normalizes relative to the submodule. No governed path
   currently lives in a submodule, and none exists in this repository; recorded as an observation.
5. **Symbolic links are not resolved.** Paths are collapsed textually (`.` and `..`), not through
   `realpath`, so a governed path reached through a symlink outside the tree is not recognised. This
   is deliberate — resolving links would make the guard's answer depend on filesystem state a tool
   call has not yet created — and it is unchanged from the previous behaviour.
6. **Pre-existing, outside this phase's scope:** `.claude/worktrees/phase7/` is an orphaned directory
   left by Phase 7. It is not a registered worktree (`git worktree list` does not show it) and it is
   untracked. It was left exactly as found.
7. **Windows can leave an empty probe directory behind.** `git worktree remove` unregisters the
   worktree and the retrying delete removes its contents, but Windows' delete-pending semantics can
   leave the now-empty directory visible in a listing after `Path.exists()` reports it gone. It is
   unregistered and harmless, and the suite clears any stale probe before creating a new one.
8. **Phase 7 blockers B-1, B-2 and B-4 are untouched.** The engineering baseline migration, the
   `<baseline-rules>` input and the TypeScript/Angular/Electron governance scope remain open. This
   phase repaired B-3 only.

---

*Produced at revision `0faf2c05fdfeaa9ec28a536ee13ba8361226756d`. No application source, test,
migration, schema, contract, architecture document, ADR, CI definition or Spec Kit asset was
modified.*

PHASE 8 COMPLETE — WORKTREE ENFORCEMENT VERIFIED
