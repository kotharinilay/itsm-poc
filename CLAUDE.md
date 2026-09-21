# Synthia — working agreement

Read `.claude/rules/00-authority.md` first. It is the authority model in full; this file is the map.

## 1. Architecture authority

Exactly three documents. Nothing else is architecture authority.

| Ref | Document |
|---|---|
| **A1** | `docs/architecture/identity-plane-final.md` — principal, tenant binding, authority, work-item immutability |
| **A2** | `docs/architecture/Synthia-OverallArchitecture-final.md` — topology, zones, trust boundaries, the stores |
| **A3** | `docs/architecture/RagAgent-Architecture-final.md` — graph topology and state, node contracts, execution authority, retrieval, release gates, ADR-001…ADR-012 inline |

`docs/architecture/integrations-service-delta.md` and `docs/architecture/ragcore-langgraph-flow.md`
sit in that directory and carry **no** authority.

## 2. Engineering baseline sources

`principles.yaml`, `dotnet.yaml`, `dotnet_lang.yaml`, `python.yaml`, `python_lang.yaml`, and the
explicit baseline block in `docs/migration/phase-9-baseline-input.md`. Migrated into
`.claude/rules/` in Phase 9; the mapping is `docs/migration/phase-9-baseline-coverage.md`.

The **frontend baseline** (TypeScript, Angular, Electron) was migrated separately in Phase 12 from
the frontend blocks of the retired Spec Kit constitution, under
`docs/adr/0010-frontend-engineering-baseline.md`; the mapping is
`docs/migration/phase-12-spec-kit-decoupling.md`. **Migration input is not authority** — the
constitution remains non-authoritative (`00-authority.md` §00.4).

## 3. Authority hierarchy

```text
Architecture question   →  A1 / A2 / A3, the section that OWNS the subject
Engineering question    →  .claude/rules/  (language-specific file > repository-wide file)
What the code does today →  docs/functional/implemented.md   (records; authorizes nothing)
```

**Existing implementation is evidence of what is, never authority for what should be.** A green
build, an existing suppression, a precedent in the tree — none is permission. Conflicting
authorities: **stop, record both sides, do not pick a winner** (`00-authority.md` §00.6).

## 4. `.claude/rules/` — persistent engineering and governance policy

| File | Scope |
|---|---|
| `00-authority.md` | repository-wide — authority, precedence, conflicts, deviations |
| `10-principles.md` | repository-wide — P1–P32, plus Conventional Commits, SemVer, Diátaxis, C4 |
| `20-dotnet.md` | **.NET / C# only** — `dotnet/**` |
| `21-python.md` | **Python only** — `ragcore/**`, `integrations/**` |
| `22-web-typescript.md` | **frontend, both clients** — `apps/**`: shared client rules + TypeScript |
| `23-angular.md` | **Angular only** — `apps/web/**` |
| `24-electron.md` | **Electron only** — `apps/desktop/**` |
| `30-langgraph.md` | LangGraph workflow change control |
| `40-testing.md` | repository-wide testing policy |
| `50-database.md` | database engineering and change control |
| `60-architecture-gates.md` | cross-gate ordering, conformance findings |
| `70-adr.md` | ADR requirements and change governance |
| `80-security-ops.md` | repository-wide security and operational policy |
| `90-functional-knowledge.md` | the implemented-truth record |

Each language file states the paths it governs, and carries a `paths:` frontmatter block so it
**loads only when Claude touches those files**. The nine repository-wide rules above carry no
`paths:` and load every session. Five of them (`00`, `10`, `40`, `60`, `80`) state policy that
applies to any change; the four gate rules (`30`, `50`, `70`, `90`) are detected *before* a file is
opened, so scoping one to the paths it governs would load it only after the moment it exists to
catch.

**A rule is never carried to another stack by analogy.** A rule you cannot see does not cease to
apply — open the file for the stack you are working in.

## 5. `.claude/skills/` — procedural workflows

`db-change`, `langgraph-change`, `adr-author`, `functional-update`. A skill is a procedure for
applying a rule; it is never authority, and rule text is not duplicated into it.

## 6. Database change gate — `.claude/rules/50-database.md`

```text
DETECT (before any application code) → STOP → DESCRIBE full impact
  → explicit human APPROVAL → implement and validate the DATABASE FIRST
  → only then continue application implementation
```

Alembic under `ragcore/migrations/` is the single schema mechanism; the .NET side owns no
migrations; migrations run as a gated job before revision activation, never at startup. Identity-
bearing work-item fields are immutable at the **database permission boundary** (A1 §12.2) — changing
that is an ADR, not an approval.

## 7. LangGraph change gate — `.claude/rules/30-langgraph.md`

```text
DETECT → STOP → DESCRIBE → CLASSIFY (workflow-only vs architecture-altering)
  → APPROVE → ADR first if architecture-altering → IMPLEMENT → TEST → VERIFY
```

Nodes, edges, routing, topology, state shape or semantics, interrupts, resume, execution ordering,
termination, clarify loop, retrieval/resolution routing, approval flow, execution treatment,
checkpoint persistence, side-effect boundaries. **The LLM never owns execution authority.** §30.4
lists the seventeen triggers that require an ADR.

When a change touches both the graph and checkpoint persistence, **DB ordering wins**
(`60-architecture-gates.md` §60.3).

## 8. ADR requirements — `.claude/rules/70-adr.md`

MADR in `docs/adr/`, four-digit sequential numbering (next: **0010**), a status field, and
`Context` / `Decision` / `Consequences`. Required **before implementation** for an architecture,
identity/authority, engineering-baseline, LangGraph-architecture or DB-authorization-boundary
decision.

**Claude writes the ADR with status `Proposed`. A human accepts it. Those are two events and the
second is not Claude's.** Approval and acceptance are never inferred — not from the request, a plan,
silence, a satisfied hook, or the session running unattended.

## 9. Functional source of truth

`docs/functional/implemented.md` — what the repository demonstrably does today. Updated **after**
verified implementation, never before, never alongside. It records; it authorizes nothing, and
updating it never substitutes for a gate.

## 10. Retired Spec Kit artifacts are not authoritative

`.specify/**` and `specs/**` remain in the tree pending a later retirement phase. They are history —
not architecture authority, not engineering baseline, not evidence of implemented behavior.

The ten `speckit-*` skills were removed in Phase 12, and **no live Claude rule, skill, hook or
setting depends on Spec Kit** (`docs/migration/phase-12-spec-kit-decoupling.md`). Source comments
and lint messages under `apps/**` and `.github/workflows/**` still cite `constitution Principle
VII`; those are stale pointers to rules that now live in `22-web-typescript.md`, `23-angular.md`
and `24-electron.md`. Cite the rule files, never the constitution.

## Non-negotiables

- **Never weaken a test** to make a change pass — no deletion, `skip`, `xfail`, loosened assertion
  or narrowed fixture (`40-testing.md` §40.1).
- **Never infer approval or acceptance** (`00-authority.md` §00.10).
- **Record deviations; do not silently repair them and do not rewrite the baseline to match the
  code** (`00-authority.md` §00.7).
- **Satisfying a hook is not approval.** H2, H3 and H5 make a gate visible; they judge nothing.
