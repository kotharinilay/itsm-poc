# 00 — Authority, source hierarchy and conflict handling

**Scope: repository-wide. This file governs every path in the repository and every stack.**

This file states *where authority comes from*. It does not restate the rules that the authorities
own — those live in the other files in `.claude/rules/`. It is the file to read first when two
sources appear to say different things.

Migrated in Phase 9 (`docs/migration/phase-9-baseline-coverage.md`). The Phase 2 authority model
(`docs/migration/phase-2-authority-model.md`) is the design record behind it.

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
`docs/current-implementation/**`, the retired Spec Kit constitution, or `docs/adr/0001`…`0009`
(historical records — see `.claude/rules/70-adr.md` §70.1).

That two of the non-authoritative files sit inside `docs/architecture/` does not promote them.

## 00.3 Engineering-baseline authority

The engineering baseline is the migrated `.claude/rules/` baseline, together with the five rule
packs and the explicit baseline block it was migrated from in Phase 9:

| Source | File | Rule-ID space |
|---|---|---|
| Repository-wide principles | `principles.yaml` | `principles#P1`…`P32` |
| .NET profile / toolchain | `dotnet.yaml` | `dotnet.yaml#baseline`, `dotnet.yaml#toolchain.*`, `P-DN-S1`…`S5`, `P-DN-1`…`6` |
| .NET language rules | `dotnet_lang.yaml` | `lang/dotnet#DN1`…`DN37` |
| Python profile / toolchain | `python.yaml` | `python.yaml#baseline`, `python.yaml#toolchain.*`, `P-PY-S1`…`S3`, `P-PY-1`…`6` |
| Python language rules | `python_lang.yaml` | `lang/python#PY1`…`PY25` |
| Explicit baseline block | `docs/migration/phase-9-baseline-input.md` | `BL-01`…`BL-38` (Phase 9 migration IDs) |

`BL-*` identifiers are **assigned by the Phase 9 migration**, because the source block carries no
IDs of its own. They live in `docs/migration/phase-9-baseline-coverage.md` and in the rule files
that carry the requirement. They are **not** written back into the source YAML or the input block.

The rule files in `.claude/rules/` are the operative statement of the baseline. The sources above
are what they were migrated from, and are the tiebreaker if a rule file is ever found to have lost
a requirement.

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
- **The retired Spec Kit artifacts are not authoritative.** `.specify/**` and `specs/**` were
  **deleted from the tree in Phase 16**
  (`docs/migration/phase-16-principle-ix-migration-and-spec-kit-retirement.md`); they survive only
  in git history, and nothing may cite them. They were never authority while they existed, and
  deletion does not change that — it removes the temptation. The ten `speckit-*` skills that
  installed the Spec Kit mechanism inside the Claude surface were **removed in Phase 12**
  (`docs/migration/phase-12-spec-kit-decoupling.md`), and no live Claude rule, skill, hook or
  setting depends on Spec Kit. The frontend requirement text that `.specify/memory/constitution.md`
  once held alone was migrated in the same phase under
  `docs/adr/0010-frontend-engineering-baseline.md`; **migration input is not authority**, and the
  constitution's non-authoritative status above is unchanged by it.

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

Phase 9 recorded editorial defects and genuine conflicts. They are listed in
`docs/migration/phase-9-baseline-coverage.md` §8 and §9 and are **open**.

## 00.7 Deviations

A deviation is a place where the implementation or its configuration does not meet the baseline.

```text
Record it.  Preserve the baseline.  Do not rewrite the baseline to match the code.
Do not "fix" the application code as a side effect of finding it.
Do not downgrade the rule because the implementation currently differs.
```

Known deviations carried forward from Phase 9 are listed in
`docs/migration/phase-9-baseline-coverage.md` §8. Closing one is a separate, human-directed act; the
ones that would weaken a baseline rule need an ADR first.

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
