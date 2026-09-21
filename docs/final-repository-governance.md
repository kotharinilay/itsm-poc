# Final repository governance

**One page, permanent, current.** It states who governs what, and points at the file that owns each
answer. **It duplicates none of them, and it is not authority for anything.**

If this page and an authority ever disagree, the authority is right and this page is a defect to
correct.

---

## 1. The authority model

| Question | Answered by | Never answered by |
|---|---|---|
| What should this platform **be**? | `docs/architecture/identity-plane-final.md` (A1), `docs/architecture/Synthia-OverallArchitecture-final.md` (A2), `docs/architecture/RagAgent-Architecture-final.md` (A3) | anything else in `docs/architecture/`, an ADR, a README, a plan, the code |
| How should code in it **be written**? | `.claude/rules/**` — fourteen files, listed in `CLAUDE.md` §3 | tooling configuration, an existing precedent, a green build |
| What does it **do today**? | `docs/functional/implemented.md`, from implementation evidence only | an architecture document, an ADR, this page, a prompt |
| What is **known to be unfinished**? | `docs/governance/open-items.md` | silence |

**Exactly three architecture documents.** `docs/architecture/integrations-service-delta.md` and
`docs/architecture/ragcore-langgraph-flow.md` sit in the same directory and carry no authority.
Neither do `README.md`, `Synthia-Platform-Specification.md`, `.serena/**`,
`docs/current-implementation/**`, `docs/governance/**` or `docs/adr/**`.

An ADR **records a decision** to change an authority; it never becomes one. The full model, with
precedence and conflict handling, is `.claude/rules/00-authority.md`.

## 2. Functional truth

`docs/functional/implemented.md` records what the repository demonstrably does, **after** the
behaviour is implemented, tested and verified — never before, never alongside. Only implementation
evidence supports a claim there. Architecture documents, ADRs, migration material, plans and
prompts are never evidence that something exists.

Rule: `.claude/rules/90-functional-knowledge.md`. Procedure:
`.claude/skills/functional-update/SKILL.md`.

## 3. The development conformance gate

Before generating or changing application code: read the owning architecture, read the rules for
the paths you will touch, read the functional record for what exists, read the implementation, and
compare. **If the area already deviates, stop and report rather than generate code.** `CLAUDE.md`
§5 states it in full; `.claude/rules/00-authority.md` §00.7 is the rule behind it.

## 4. The four change gates

| Gate | Rule | Skill | Guard |
|---|---|---|---|
| Database / schema | `.claude/rules/50-database.md` | `db-change` | `db_migration_guard.py` (H2) |
| LangGraph workflow | `.claude/rules/30-langgraph.md` | `langgraph-change` | `langgraph_change_guard.py` (H3) |
| Architecture / baseline decision | `.claude/rules/70-adr.md` | `adr-author` | `adr_structure_guard.py` (H5) |
| Functional record | `.claude/rules/90-functional-knowledge.md` | `functional-update` | none, deliberately |

Every one has the shape `DETECT -> STOP -> DESCRIBE -> human APPROVAL -> IMPLEMENT -> TEST ->
VERIFY`. Cross-gate ordering is `.claude/rules/60-architecture-gates.md` §60.3: **database ordering
wins**, and the functional record is last.

**A guard makes a gate visible. It judges nothing, and satisfying it is not approval.**
**Approval and acceptance are never inferred** (`.claude/rules/00-authority.md` §00.10).

## 5. Language governance

Every executable language and application stack has a governing rule, its enforcement tooling and
its scope. The matrix is `CLAUDE.md` §9. There is no executable language in this repository
without one, and adding a language needs a rule before it carries logic.

## 6. Testing

`.claude/rules/40-testing.md` owns the testing baseline: the fifteen required categories (§40.8),
the per-change obligation matrix (§40.9), what each principle owes (§40.5), and the deliberate
absence of a coverage threshold (§40.10). **A test is never weakened to make a change pass**
(§40.1) — that prohibition survives an approval, an accepted ADR and every other licence.

## 7. Documentation surfaces, and what each is for

| Surface | Holds | Updated |
|---|---|---|
| `docs/architecture/**` (A1-A3) | intended architecture | by a human, under an accepted ADR |
| `docs/adr/**` | accepted decisions and their rationale | a new record per decision; history is never rewritten |
| `.claude/rules/**` | the engineering and governance baseline | only by ADR where the rule itself changes |
| `CLAUDE.md` | durable operating guidance and the routing map | when the model changes, not per feature |
| `docs/functional/implemented.md` | current implemented behaviour | after implementation is verified |
| `docs/governance/open-items.md` | what is known to be unfinished | when an item opens or closes |
| `docs/current-implementation/**` | a navigational snapshot of the tree; **not** the functional record | when it drifts enough to mislead |
| `Synthia-Platform-Specification.md` | **history.** Retained because accepted records ADR-0001 to ADR-0008 and the ADR index cite it for their own rationale, and an accepted record is never rewritten. Retiring it is decision **UD-9** | not updated |
| `.serena/**` | navigation memories for the Serena MCP server; tooling, not governance | when the code it describes moves |

**For every completed feature, update only what genuinely changed.** Do not mechanically touch
every governance document after every feature; documentation churn makes the current-state record
harder to trust, not easier.

## 8. MCP tooling

`.mcp.json` declares **Serena** (repository-aware code navigation) and **Figma**
(`https://mcp.figma.com/mcp`, design reference for the client surfaces). Both are tooling. Neither
is authority, neither overrides a rule or an ADR, and neither is evidence of implemented behaviour.
No credential for either is committed; Figma authenticates interactively.

**Declaring a server is not connecting it. Verify with `/mcp` in Claude Code.** `CLAUDE.md` §13
states when to reach for each.

## 9. CI/CD

CI/CD is defined in `azure-pipelines/`, one pipeline per concern. `.github/workflows/**` remains
the currently authoritative execution surface until the Azure DevOps pipelines have run and parity
is proven against `azure-pipelines/PARITY.md`, whose criteria are the condition for deleting
`.github/`.

A pipeline is **where a gate runs**. The rule that requires the gate lives in `.claude/rules/**`,
and **a passing pipeline is never evidence that a rule is met**
(`.claude/rules/00-authority.md` §00.4).

## 10. What this repository will not do

- Reconcile architecture to implementation, or implementation to architecture, on its own
  initiative. A difference is a **conformance finding**: recorded, not resolved
  (`.claude/rules/60-architecture-gates.md` §60.4).
- Repair a baseline deviation silently, or rewrite a rule to match the code
  (`.claude/rules/00-authority.md` §00.7).
- Pick a winner between two conflicting authorities (§00.6).
- Treat a hook, a plan, a prompt or silence as approval (§00.10).
