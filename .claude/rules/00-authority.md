# 00 — Authority, source hierarchy and conflict handling

**Scope: repository-wide. This file governs every path in the repository and every stack.**

This file states *where authority comes from*. It does not restate the rules that the authorities
own — those live in the other files in `.claude/rules/`. It is the file to read first when two
sources appear to say different things.

Everything open — every deviation, enforcement gap, source defect, conflict and human decision this
model has produced and not closed — is registered in `docs/governance/open-items.md`. That register
is not authority; it is the list of things this file's rules say must be recorded rather than
repaired.

---

## 00.1 The two authority domains

There are exactly two, and they are not interchangeable.

| Domain | Question it answers | Authority |
|---|---|---|
| **Architecture** | What *should* this platform be? | A1, A2, A3 (§00.2) |
| **Engineering baseline** | How *should* code in it be written? | The migrated `.claude/rules/` baseline (§00.3) |

Neither domain overrides the other, because they answer different questions. An architecture
document does not decide whether a `catch` block may be empty; an engineering rule does not decide
where a store lives.

## 00.2 Architecture authority

Exactly three documents are architecture authority:

| Ref | Document | Owns |
|---|---|---|
| **A1** | `docs/architecture/identity-plane-final.md` | The principal, tenant binding, authority semantics, the work item's identity-bearing fields and their immutability |
| **A2** | `docs/architecture/Synthia-OverallArchitecture-final.md` | Platform topology, zones, trust boundaries, the stores and their classification, residency and lifecycle |
| **A3** | `docs/architecture/RagAgent-Architecture-final.md` | Graph topology and state, node contracts, the execution authority boundary as RagCore observes it, retrieval architecture, the evaluation harness and release gates, and ADR-001…ADR-012 inline |

**No other repository document is architecture authority.** Specifically not:
`docs/architecture/integrations-service-delta.md`, `docs/architecture/ragcore-langgraph-flow.md`,
`README.md`, `Synthia-Platform-Specification.md`, `.serena/**`,
`docs/current-implementation/**`, `docs/governance/**`, or `docs/adr/0001`…`0009`
(historical records — see `.claude/rules/70-adr.md` §70.1).

That two of the non-authoritative files sit inside `docs/architecture/` does not promote them.

## 00.3 Engineering-baseline authority

**`.claude/rules/**` is the engineering baseline. It is the whole of it, and nothing outside it is.**

The fourteen rule files in that directory state every engineering requirement in force. There is no
second source to consult, no pack to cross-check, and no file elsewhere in the tree that a rule
defers to for its own content.

### Rule identifiers

Each requirement carries an identifier, and those identifiers are **defined by these files**:

| Space | Stated in | Covers |
|---|---|---|
| `P-1`…`P-32` | `10-principles.md` | language-independent design principles |
| `C-1`…`C-6` | `10-principles.md` | repository-wide conventions — commits, versioning, docs, diagrams, ADR format |
| `H-1`, `H-2` | `10-principles.md` §10.7 | implementation honesty and reference fixtures |
| `DN-1`…`DN-37`, `P-DN-S1`…`S5` | `20-dotnet.md` | .NET language and strictness rules |
| `PY-1`…`PY-25`, `P-PY-S1`…`S3` | `21-python.md` | Python language and strictness rules |
| `BL-01`…`BL-39` | `20-dotnet.md`, `80-security-ops.md` | platform, data-access, observability, container and operational rules |
| `FE-SH-*`, `FE-TS-*`, `FE-NG-*`, `FE-EL-*` | `22-web-typescript.md`, `23-angular.md`, `24-electron.md` | the frontend baseline |
| `TC-01`…`TC-15`, `CM-01`…`CM-12` | `40-testing.md` | required test categories and per-change obligations |

An identifier is cited by its rule file and section. **Nothing in the repository reads, parses or
loads a rule from anywhere else.**

### Origin lines

Most rules carry an `*Origin:*` line naming the material the requirement was migrated from. Those
inputs — the five root rule packs, an explicit baseline block, and a retired frontend/testing
document — **were retired from the tree and survive only in git history.**

```text
An Origin line is provenance.  It is NOT a citation of authority, it is NOT a place to look
something up, and a rule never means what it means because of what its origin said.
The rule text in .claude/rules/ IS the requirement.
```

Where a rule's origin was an accepted decision rather than a retired pack, the `Origin:` line names
that ADR — `ADR-0010` (frontend), `ADR-0011` (testing categories), `ADR-0012` (`H-1`/`H-2`). An ADR
is the instrument that authorized the rule; it still is not the rule
(`.claude/rules/70-adr.md` §70.1).

## 00.4 What is never authority

- **Existing implementation is evidence of what *is*, never authority for what *should be*.** That
  a suppression already exists, that a rule is already violated somewhere, that CI currently passes
  with the violation in place — none of these is permission. They are deviations to report
  (§00.7), never a precedent to extend.
- **A green build is not authority.** A gate that does not fire proves nothing about the rule.
- **`docs/functional/implemented.md` is not authority.** It records what the repository
  demonstrably does today, and it authorizes nothing. See `.claude/rules/90-functional-knowledge.md`.
- **Configuration is not authority for the baseline.** `.editorconfig`, `Directory.Build.props` and
  `pyproject.toml` *realize* the baseline; where they differ from it, the baseline stands and the
  difference is a deviation.
- **Generated or untracked residue is not evidence of anything.** Establish repository content with
  `git ls-files`, not by walking the working tree: `bin/`, `obj/`, `.venv/`, `__pycache__/`,
  `node_modules/` and packaging output are excluded.
- **Retired governance material is not authority, and is not evidence of anything.** Material this
  repository once governed itself with — earlier rule packs, an earlier specification-driven
  workflow and its templates, earlier migration records — has been removed from the tree. It
  survives in git history, where it may be read for history and **may not be cited**: not as
  architecture, not as the baseline, not as evidence of implemented behaviour, and not as the
  reason a current rule says what it says. A requirement that matters is stated here, now, in
  `.claude/rules/**`.
- **`docs/governance/open-items.md` is not authority.** It registers what is open — deviations,
  enforcement gaps, defects, conflicts and the decisions that would close them. An open item is
  never permission to extend the thing it records.

## 00.5 Precedence

Within a domain, the more specific source wins over the more general:

```text
Architecture:         A1/A2/A3 section that OWNS the subject
                        > another authoritative document's cross-reference to it
                        > everything else (which is not authority at all)

Engineering baseline: language-specific rule file (20-dotnet.md, 21-python.md)
                        > repository-wide rule file (10-principles.md, 40-testing.md,
                          80-security-ops.md)
                        > the source pack it was migrated from
```

A deferral is not a conflict. A3 §6.3 deferring to A1 for identity and authority rules is the
ownership model working, not two documents disagreeing.

A language-specific rule file never *relaxes* a repository-wide rule; it states how that rule is met
on that stack, or it adds to it. If a language rule would genuinely relax a repository-wide one,
that is a baseline change and needs an ADR (`.claude/rules/70-adr.md` §70.2 B).

## 00.6 Conflict handling — stop, do not choose

When two authoritative sources genuinely conflict:

```text
1. STOP.  Do not implement the affected change.
2. RECORD: source A (file + section), source B (file + section), the exact conflict,
           the affected stack, the impact, and the human decision required.
3. An ADR resolves it — .claude/rules/70-adr.md §70.2 A(8). A human accepts it.
```

**Never pick a winner silently.** This applies to a conflict between two architecture documents,
between two baseline sources, and between a baseline source and a mandatory governance rule.

**A cross-reference error, a filename mismatch, a truncated sentence or a mis-pointed identifier is
an editorial defect, not a conflict.** It needs a human editorial correction, not an ADR. Report it;
do not repair the authoritative source on your own initiative.

Known editorial defects and the one genuine open conflict are registered in
`docs/governance/open-items.md` §3 and §4. They are **open**, and recording one there is not
closing it.

## 00.7 Deviations

A deviation is a place where the implementation or its configuration does not meet the baseline.

```text
Record it.  Preserve the baseline.  Do not rewrite the baseline to match the code.
Do not "fix" the application code as a side effect of finding it.
Do not downgrade the rule because the implementation currently differs.
```

Known deviations are registered in `docs/governance/open-items.md` §1, with the enforcement gaps
that accompany them in §2. Closing one is a separate, human-directed act; the ones that would weaken
a baseline rule need an ADR first.

## 00.8 Rules, skills and hooks

| Location | Holds | Is it authority? |
|---|---|---|
| `.claude/rules/**` | Persistent engineering and governance policy | Yes — the operative baseline |
| `.claude/skills/**` | Repeatable procedures (ADR authoring, DB change, LangGraph change, functional update) | No — a procedure for applying a rule |
| `.claude/hooks/**` | Deterministic guards that make a gate fire | No — **satisfying a hook is never approval** |

Rule text is not duplicated into a skill, and a skill's procedure is not duplicated into a rule.
Where a rule names its procedure, it names it by path and stops there.

## 00.9 The gates, and where they are defined

Each gate is defined in exactly one file. This table is a pointer, not a restatement.

| Gate | Defined in | Procedure |
|---|---|---|
| Database / schema change | `.claude/rules/50-database.md` | `.claude/skills/db-change/SKILL.md` |
| LangGraph workflow change | `.claude/rules/30-langgraph.md` | `.claude/skills/langgraph-change/SKILL.md` |
| Architecture / baseline decision (ADR) | `.claude/rules/70-adr.md` | `.claude/skills/adr-author/SKILL.md` |
| Functional record update | `.claude/rules/90-functional-knowledge.md` | `.claude/skills/functional-update/SKILL.md` |
| Cross-gate ordering | `.claude/rules/60-architecture-gates.md` | — |

## 00.10 Approval and acceptance are never inferred

Approval means a human said so, in this session, about this change. Acceptance of an ADR means a
human accepted that decision, in this session.

None of the following is approval or acceptance: the task description implying the change; a prior
approval for a different change; the change being "obviously needed"; an existing precedent in the
tree; silence; an unanswered question; an accepted plan that did not enumerate the change; the
permission mode in force; the session running unattended; a satisfied hook.

This is the same non-inference rule as `.claude/rules/50-database.md` §50.2,
`.claude/rules/30-langgraph.md` §30.5 and `.claude/rules/70-adr.md` §70.3, and it applies here
unchanged. Claude writes an ADR; Claude does not accept one.
