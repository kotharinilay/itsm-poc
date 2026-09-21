# 10 — Language-independent engineering principles

**Scope: repository-wide.** Every rule in this file applies to every stack in this repository —
`.NET / C#` (`dotnet/**`), Python (`ragcore/**`, `integrations/**`), TypeScript / Angular
(`apps/web/**`), Electron (`apps/desktop/**`), and any future stack — unless the rule's own
**Applies when** line narrows it.

Source: `principles.yaml`, which is language-agnostic by construction (`applies_when: [always]` on
most entries). Where a stack has a specific mechanism for meeting one of these principles, that
mechanism is stated in `.claude/rules/20-dotnet.md` or `.claude/rules/21-python.md` and cites the
principle it realizes. A language file never relaxes a principle here
(`.claude/rules/00-authority.md` §00.5).

**Traceability.** Every rule carries `Source: <baseline rule id>`. The full mapping is
`docs/migration/phase-9-baseline-coverage.md`.

**Tier** is the source's own `tier` field: `core` rules are the non-negotiable set; `extended` rules
are equally binding but were tiered as secondary in the source. Tier does not create an exemption.

**Enforcement** states what actually gates the rule in this repository today, using the vocabulary
in `docs/migration/phase-9-baseline-coverage.md` §5: `mechanical`, `partial`, `procedural`,
`currently-unenforced`. It is an honest statement of the gate, not an aspiration. A rule whose
enforcement is `procedural` is not optional — it is reviewed rather than gated.

---

## 10.1 Design and structure

### P-1 — Single reason to change
**A module has one reason to change; group what changes together and separate what changes for
different reasons.**
Give each class/module a single axis of change tied to one actor or stakeholder. When a type
accumulates unrelated responsibilities (persistence + formatting + policy), split it into
collaborators behind narrow interfaces. Keep methods short and functions doing one thing; route
cross-cutting concerns (logging, transactions) through decorators/middleware, not inline.
*Source: `principles#P1` · tier core · applies when: always · Enforcement: partial (size/complexity
proxies only; single-reason-to-change itself is review)*

### P-2 — Open for extension, closed for modification
**Add behavior via new code, not edits to tested code.**
Introduce new behavior by adding a new implementation of an existing abstraction (a new strategy,
handler, or subtype) rather than editing a switch/if-ladder or a stable, tested class. Design
variation points as interfaces or abstract seams up front where variation is expected; keep the
stable core untouched when requirements grow.
*Source: `principles#P2` · tier extended · applies when: public-contract-change · Enforcement:
procedural*

### P-3 — Substitutability
**Subtypes must be substitutable for their base types without breaking a caller's correctness
expectations.**
A subtype must honor the base type's contract: do not strengthen preconditions, weaken
postconditions, throw where the base does not, or return sentinels the base forbids. If a subtype
cannot fulfill the contract, it is not a subtype — model it as a sibling. Write one contract test
suite against the base abstraction and run it against every implementation.
*Source: `principles#P3` · tier extended · applies when: domain-model · Enforcement: procedural —
the source requires a shared behavioral contract suite executed against every implementation
(`.claude/rules/40-testing.md` §40.5); substitutability is a runtime property no structural proxy
discharges*

### P-4 — Interface segregation
**No client is forced to depend on methods it does not use; prefer many small role-focused
interfaces over one fat interface.**
Define interfaces around a single caller's role, not around an implementation's full surface. When
one consumer uses only a slice of a wide interface, extract that slice into its own interface and
depend on it. Avoid "header" interfaces that mirror every public method of a class.
*Source: `principles#P4` · tier extended · applies when: public-contract-change · Enforcement:
procedural*

### P-5 — Dependency inversion
**High-level policy depends on abstractions, not on infrastructure detail; both depend on
abstractions.**
Domain/application code references only interfaces it owns; concrete infrastructure (persistence,
HTTP, messaging, vendor SDK types) is injected and lives at the outer edge. Never import an
infrastructure namespace/package into a domain type. Define the port (interface) in the inner layer
and implement the adapter in the outer layer, wiring at the composition root.
*Source: `principles#P5` · tier core · applies when: domain-model, cross-module-write ·
Enforcement: mechanical (architecture/boundary suites fail the build when a domain module
references an infrastructure namespace or concrete adapter type)*

### P-6 — One authoritative representation (DRY, bounded)
**Every piece of knowledge has one authoritative representation; do not duplicate a concept across
the codebase.**
Represent each business rule, constant, or schema once and reference it. Before copying a block,
name the shared concept and extract it — **but only within a module boundary and only at the
rule-of-three**: two occurrences may stay; a forced abstraction over an unnamed concept is worse
than duplication. **Do not DRY across module/service boundaries** — that recouples them.
*Source: `principles#P6` · tier core · applies when: always · Enforcement: partial (token/AST
duplication detection only; semantic duplication and the boundary caveat are review)*

### P-7 — Simplicity
**Prefer the simplest design that satisfies the requirement; complexity must be justified.**
Reach for the plainest construct first — a function before a class, a class before a framework, a
direct call before an event. Cap nesting and branching; flatten with early returns and guard
clauses. Do not add configuration knobs, indirection layers, or generality that the current
requirement does not exercise.
*Source: `principles#P7` · tier core · applies when: always · Enforcement: partial
(complexity/nesting thresholds as a proxy)*

### P-8 — No speculative capability (YAGNI)
**Do not build a capability until a current requirement needs it.**
Implement only what the accepted requirement demands. Do not add speculative parameters, extension
points, config flags, or "future-proof" abstractions with no present caller. Delete dead/unreachable
code and unused public surface rather than keeping it "just in case."
*Source: `principles#P8` · tier core · applies when: always · Enforcement: partial (unreachable
code and unused non-public members are flagged; "has a present caller" is review)*

### P-9 — Tell, don't ask
**Tell an object what to do rather than asking it for its data and acting on that data elsewhere.**
Put behavior next to the data it operates on. Instead of pulling fields out of an object and making
decisions about them in a caller, expose an intention-revealing method on the object that
encapsulates the decision. Avoid long getter chains feeding external conditionals (feature envy).
*Source: `principles#P9` · tier extended · applies when: domain-model · Enforcement: procedural*

### P-10 — Composition over inheritance
**Favor object composition over class inheritance for reuse and variation.**
Reuse behavior by holding a collaborator and delegating, not by extending a base class. Reserve
inheritance for genuine substitutable is-a relationships (see P-3); model has-a and capabilities via
composition and interfaces. Avoid deep inheritance hierarchies and protected mutable state shared
with subclasses.
*Source: `principles#P10` · tier extended · applies when: domain-model · Enforcement: procedural*

### P-11 — Fail fast
**Surface errors and invalid state at the earliest point they can be detected.**
Validate arguments and preconditions at the top of a function/boundary with guard clauses and fail
immediately on violation; do not let bad input propagate to be re-checked deeper. Prefer
non-nullable parameters and typed inputs so absence is caught at the boundary rather than as a null
dereference later.
*Source: `principles#P11` · tier core · applies when: error-path, user-input · Enforcement: partial
(nullability analysis; `.claude/rules/20-dotnet.md` DN-16 and `.claude/rules/21-python.md` PY-3 are
the stack mechanisms)*

### P-12 — Law of Demeter
**A method talks only to its immediate collaborators, not to objects reached by navigating an object
graph.**
Call methods on your own fields, parameters, and objects you create — not on the return values of
those (no `a.getB().getC().doThing()` train wrecks). If you need something deep, expose a method on
the immediate collaborator that returns it or does the work, keeping knowledge of the graph local.
*Source: `principles#P12` · tier extended · applies when: always · Enforcement:
currently-unenforced — the source requires a lint/arch check for graph-navigation chains; no such
check exists in this repository today*

### P-13 — Separation of concerns
**Distinct concerns live in distinct modules or layers so each can be reasoned about and changed
independently.**
Assign one concern per module/layer (presentation, application, domain, infrastructure) and route
interaction through explicit boundaries. Do not mix transport, business rules, and persistence in
one unit. A change to one concern should not force edits across unrelated layers.
*Source: `principles#P13` · tier core · applies when: cross-module-write, domain-model ·
Enforcement: mechanical (layering/boundary suites fail the build on a forbidden cross-layer
reference)*

### P-14 — Least astonishment
**Behave the way a reasonable user of the code expects; avoid surprising side effects and
inconsistent conventions.**
Make names describe exactly what a member does; do not hide mutation, I/O, or state change behind an
innocuous-looking accessor. Keep parameter order, return conventions, and error signaling consistent
with the rest of the codebase and the platform's idioms so callers are not caught out.
*Source: `principles#P14` · tier extended · applies when: always · Enforcement: procedural*

### P-15 — Command/query separation
**A method either returns data or changes observable state, never both.**
Split commands from queries: a query returns a value and is side-effect free and safely repeatable;
a command changes state and returns void (or only a status/id). Do not mutate state inside a getter
or return domain results from a state-changing operation, so callers can read without fear of side
effects.
*Source: `principles#P15` · tier extended · applies when: always · Enforcement: procedural*

### P-16 — Single level of abstraction
**All statements in a function operate at a single level of abstraction.**
Do not mix high-level policy with low-level detail in one function. If a function orchestrates
steps, each step is a well-named call at the same altitude; push byte/loop/parsing detail down into
helpers. A reader should be able to follow one function as a short paragraph of intent.
*Source: `principles#P16` · tier extended · applies when: always · Enforcement: partial (length and
nesting depth as a proxy)*

## 10.2 Encapsulation, access and data

### P-17 — Least privilege (repository-wide)
**Grant each component the minimum rights, access, and visibility it needs to do its job.**
Default every type, member, and field to the most restrictive access modifier that still works
(`private`/`internal` before `public`; `sealed`/`final` unless designed for extension); widen only
on demonstrated need. Scope credentials, tokens, and infrastructure permissions to the narrowest
resource and action set. **Never grant broad or wildcard rights for convenience.**

This principle is **repository-wide and not confined to the database.** It governs code visibility
in every stack, cloud/managed-identity role assignments, Service Bus and Key Vault access policies,
container capabilities, CI token scopes, and browser/renderer privileges in
`apps/web` and `apps/desktop`. The database-principal separation in `.claude/rules/50-database.md`
§50.7 is **one instance** of this principle, not its whole extent.
*Source: `principles#P17` · tier extended · applies when: always · Enforcement: partial (database
principals are mechanically separated; code-visibility and cloud-scope breadth are not gated
repository-wide — see `.claude/rules/80-security-ops.md` §80.2)*

### P-18 — Information hiding
**Hide implementation behind a stable interface and isolate the parts most likely to change.**
Expose intent through a narrow public interface and keep data and mechanism private. No public
mutable fields; expose behavior, not internal representation. Group volatile design decisions
(formats, algorithms, vendor specifics) behind a module boundary so callers are insulated when they
change.
*Source: `principles#P18` · tier extended · applies when: always · Enforcement: partial*

### P-19 — Program to an interface
**Depend on abstractions for collaborators, programming to an interface rather than a concrete
implementation.**
Type fields, parameters, and return values of collaborators as the interface/abstract type, not the
concrete class, so implementations are substitutable and testable with fakes. Construct concrete
types only at the composition root; the rest of the code names only abstractions.
*Source: `principles#P19` · tier extended · applies when: domain-model, external-call ·
Enforcement: partial (composition-root suites gate where concrete types may be constructed)*
> Read together with `.claude/rules/20-dotnet.md` DN-33, which asks for a concrete type **only**
> where an analyzer proves the dispatch is avoidable. Genuine seams stay abstract; P-19 wins at a
> seam.

### P-20 — Make illegal states unrepresentable
**Use the type system so invalid data cannot be constructed; parse input into precise types at the
boundary.**
At each boundary, parse raw input once into a domain type that can only hold valid values (value
objects, non-empty collections, closed unions/enums, smart constructors) and pass that type inward —
do not pass primitives and re-validate. Prefer the most precise type that makes illegal combinations
unrepresentable rather than validating with scattered runtime checks.
*Source: `principles#P20` · tier core · applies when: domain-model, user-input, serialization ·
Enforcement: partial (nullability/exhaustiveness analysis; the parse-at-the-boundary obligation is
structural test + review)*

### P-25 — Immutable by default
**Data is immutable by default; expose mutation only where a mutable model is genuinely required.**
Model domain and DTO types as immutable value objects — set all state at construction, expose
read-only members, and return new instances for changes rather than mutating in place. Reserve
mutable state for a deliberately-scoped, single-threaded owner. Immutable data is safe to share
across threads and cannot drift into an invalid state after construction (reinforces P-20).
*Source: `principles#P25` · tier core · applies when: domain-model, concurrency · Enforcement:
partial*

### P-32 — Explicit contracts
**Public operations declare and enforce their preconditions, postconditions, and invariants as an
explicit contract.**
Specify each public operation's contract and enforce it in code: check preconditions at entry (see
P-11), assert postconditions on the returned result, and maintain a class/aggregate invariant that
holds before and after every public call. Express contracts as executable checks or the contract
construct the stack affords, so violations surface as failures rather than silent corruption.
*Source: `principles#P32` · tier extended · applies when: public-contract-change, domain-model ·
Enforcement: partial — the source requires both a structural check and an integration test
exercising each operation against its contract (`.claude/rules/40-testing.md` §40.5)*

## 10.3 Coupling, cohesion and dependencies

### P-24 — High cohesion, low coupling
**Group strongly related responsibilities together and minimize dependencies between modules.**
Keep members that change and are used together in the same module (high cohesion); expose a small
surface and depend on few other modules through narrow interfaces (low coupling). Avoid a module
that reaches into many others or is reached into by many; break bidirectional and cyclic
dependencies.
*Source: `principles#P24` · tier extended · applies when: always · Enforcement: mechanical
(module-isolation and boundary suites fail on dependency cycles and forbidden cross-module
references)*

### P-26 — Explicit injected dependencies; no service locator
**Dependencies are explicit and injected; components never reach out to hidden global state or a
service locator.**
Declare every collaborator a component needs as a constructor parameter (or equivalent explicit
input) so its dependencies are visible and substitutable in tests. Do not resolve services from a
static container/service locator, ambient singleton, or mutable global inside business code; resolve
and wire only at the composition root.
*Source: `principles#P26` · tier extended · applies when: always · Enforcement: mechanical
(architecture suites fail on service-locator resolution outside the composition root)*
> The .NET realization — constructor injection as the sole pattern, the built-in
> `Microsoft.Extensions.DependencyInjection` container, and the named anti-patterns — is
> `.claude/rules/20-dotnet.md` §20.2 (`BL-02`).

### P-23 — Convention over configuration
**Provide sensible defaults so a developer configures only the exceptions, not the norm.**
Follow the framework's and codebase's naming, folder, and wiring conventions so components are
discovered and wired by default with no explicit configuration. Introduce explicit configuration
only where behavior must deviate from the convention; do not restate defaults.
*Source: `principles#P23` · tier extended · applies when: always · Enforcement: partial (naming and
layout lint only)*

### P-22 — Leave it cleaner (Boy Scout rule)
**Leave every module you touch at least as clean as you found it.**
When editing existing code, make the small adjacent improvement the change invites — a clearer name,
a removed dead branch, a fixed warning — without scope-creeping. **Never increase the count of
analyzer/lint warnings in a file you modify; drive it down.**
*Source: `principles#P22` · tier extended · applies when: always · Enforcement:
currently-unenforced — the source names a warning-count baseline ratchet; no ratchet exists in this
repository. In .NET the warning count is structurally zero because `TreatWarningsAsErrors` is on,
which satisfies the letter of the rule on that stack but is not the ratchet the source describes*

## 10.4 Runtime behavior

### P-21 — Idempotent retryable operations
**Operations that may be retried are designed to be idempotent so repeated execution has the same
effect as one.**
For any operation a client or broker may retry, make the intended effect independent of how many
times it runs: accept an idempotency key or use a natural unique key, upsert instead of blind
insert, and de-duplicate consumed events. Reserve non-idempotent creates for cases with a genuine
dedupe guarantee upstream.
*Source: `principles#P21` · tier core · applies when: http-endpoint, persistence-write,
event-consume, external-call · Enforcement: procedural at the principle level — the source requires
an execution test asserting a single net effect across repeated runs (`.claude/rules/40-testing.md`
§40.5). The platform mechanism is `BL-28` in `.claude/rules/20-dotnet.md`; signed idempotent
execution in the graph is A3/ADR-011 via `.claude/rules/30-langgraph.md`*

### P-27 — Externalized configuration
**Configuration and environment-specific values live outside the code and are read from the
environment, never hardcoded.**
Keep no environment-specific literal — connection string, hostname/URL, port, credential, API key,
feature toggle — inline in source. Read every such value from the injected configuration abstraction
(environment variables or a config provider) and pass it inward from the composition root. **The
same build artifact must run in every environment with only its configuration changing.**
*Source: `principles#P27` · tier core · applies when: configuration, sensitive-data · Enforcement:
mechanical (secret/credential literals are lint- and scan-gated; see
`.claude/rules/21-python.md` PY-15 and `.claude/rules/80-security-ops.md` §80.3)*

### P-28 — Stateless services
**Services hold no client or session state between requests; durable state lives in a backing
store.**
Treat each request or message as self-contained: do not stash per-client state in instance fields of
a long-lived (singleton/shared) handler, in mutable module/static variables, or in in-process memory
a later request expects to find. Persist anything that must outlive the request to a datastore,
cache, or the request-scoped context so any instance can serve any request.
*Source: `principles#P28` · tier extended · applies when: http-endpoint, concurrency · Enforcement:
partial (`.claude/rules/20-dotnet.md` DN-27 gates mutable visible statics in .NET; the wider
per-request-state obligation is review)*

### P-29 — Logs as an event stream
**Diagnostic output is emitted as an event stream through the logging abstraction, never written
directly to files or the console.**
Emit logs, metrics, and traces through the injected logging/telemetry abstraction and let the
execution environment route and store them. Do not open log files, manage rotation, or write
diagnostics with raw console/stdout print calls from application code. Prefer structured events with
stable keys over interpolated free-text messages.
*Source: `principles#P29` · tier extended · applies when: logging-telemetry · Enforcement: partial
— mechanical in .NET (`.claude/rules/20-dotnet.md` DN-3 architecture suite),
**currently-unenforced in Python** (`.claude/rules/21-python.md` PY-4: ruff `T20` is not selected)*

### P-30 — No swallowed errors
**Every caught error is handled, translated, or rethrown with context; errors are never silently
swallowed.**
Never write an empty or comment-only catch/except block, and never discard a returned error or
result status. On catching, do exactly one of: recover meaningfully, translate to a
domain-appropriate error and rethrow, or rethrow preserving the original cause and stack. Do not
catch a broad/base error type to mask failures; log-and-continue only where continuing is a
deliberate, documented choice.
*Source: `principles#P30` · tier core · applies when: error-path · Enforcement: mechanical
(`.claude/rules/20-dotnet.md` DN-10/DN-26 and `.claude/rules/21-python.md` PY-2/PY-14, plus an
architecture suite asserting no swallowing catch)*

### P-31 — Deterministic resource release
**Resources with a release obligation are acquired and released deterministically within a bounded
scope, never leaked.**
Acquire any resource that must be released — connection, file/stream handle, lock, socket, cursor —
inside a scoped construct that guarantees release on every exit path, including exceptions (a
`using`/try-with-resources/defer-style block or the language's disposal contract). Do not rely on
the garbage collector or finalizers for timely release, and release in reverse order of acquisition.
*Source: `principles#P31` · tier extended · applies when: external-call, persistence-write ·
Enforcement: partial (`.claude/rules/20-dotnet.md` DN-15, `.claude/rules/21-python.md` PY-9)*

---

## 10.5 Repository-wide conventions

These are language-independent conventions that the .NET and Python packs state **identically**.
Per `.claude/rules/00-authority.md` §00.5 they are preserved **once**, here, rather than duplicated
into `20-dotnet.md` and `21-python.md`. Both source IDs are recorded on each.

They are the requirements Phase 7 found dropped (`docs/migration/phase-7-validation.md` §4.3). A
governance gate that *reacts* to a change in one of these conventions is not a substitute for the
convention itself; both are stated — the convention here, the gate in
`.claude/rules/70-adr.md` §70.2 B(6).

### C-1 — Conventional Commits
**Commit messages follow the Conventional Commits v1.0.0 specification.**

```text
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

- `type` is one of the conventional set — `feat`, `fix`, `docs`, `style`, `refactor`, `perf`,
  `test`, `build`, `ci`, `chore`, `revert`. `feat` and `fix` carry the SemVer meaning in C-2.
- `scope` is optional and parenthesised: `feat(governance): …`.
- A breaking change is marked with `!` before the colon, or a `BREAKING CHANGE:` footer, or both.
- The description is imperative, lower-case, and carries no trailing period.

*Source: `dotnet.yaml#P-DN-4`, `python.yaml#P-PY-4` · Enforcement: **currently-unenforced** — the
source names "a commit-message CI check + release tooling"; no commitlint, semantic-release or
equivalent exists in this repository (`docs/migration/phase-9-baseline-coverage.md` §8, ENFORCEMENT
GAP EG-1). The convention is binding on every commit regardless.*

### C-2 — Semantic Versioning
**Released artifacts are versioned per SemVer 2.0.0 — `MAJOR.MINOR.PATCH`.**

- `MAJOR` on an incompatible API change (the `!` / `BREAKING CHANGE:` commits of C-1).
- `MINOR` on backward-compatible added functionality (`feat`).
- `PATCH` on a backward-compatible fix (`fix`).
- Pre-release and build metadata use the SemVer suffix grammar; they never encode meaning the
  three numbers should carry.

*Source: `dotnet.yaml#P-DN-4`, `python.yaml#P-PY-4` · Enforcement: **currently-unenforced** — no
release tooling derives or checks the version. `ragcore/pyproject.toml` and
`integrations/pyproject.toml` both declare `version = "0.1.0"`, which is SemVer-shaped but not
mechanically maintained (EG-1).*

### C-3 — Documentation structure: Diátaxis
**Prose documentation is organised on the Diátaxis model** — every document is deliberately one of
four kinds, and does not silently mix them:

| Kind | Serves | Shape |
|---|---|---|
| **Tutorial** | learning | a guided lesson that succeeds by being followed |
| **How-to guide** | a goal | steps that solve one real problem |
| **Reference** | looking something up | accurate, complete, austere description |
| **Explanation** | understanding | context, rationale, alternatives |

Write a new document as one of these and say which it is. A reference page that drifts into
rationale, or a tutorial that becomes a reference, is the failure Diátaxis exists to prevent.

*Source: `dotnet.yaml#P-DN-6`, `python.yaml#P-PY-6` · Enforcement: procedural (the source states
doc structure is `pr_review`-only)*

### C-4 — Architecture diagrams: C4
**Architecture is diagrammed using the C4 model** — System Context, Container, Component and (where
warranted) Code, each at its own level and not blended into one diagram. A diagram states which C4
level it is at.

*Source: `dotnet.yaml#P-DN-6`, `python.yaml#P-PY-6` · Enforcement: procedural (diagram presence is
`pr_review`-only)*

### C-5 — README: quickstart and ADR pointer
**The README carries a quickstart and a pointer to the ADR index.** A reader must be able to get the
thing running from the README, and must be able to find `docs/adr/` from it.

*Source: `dotnet.yaml#P-DN-6`, `python.yaml#P-PY-6` · Enforcement: procedural*

### C-6 — ADR format
**Architecture decisions are recorded as MADR records in `docs/adr/`, sequentially numbered, each
with a status field.**

The full procedure — numbering, filename grammar, the closed status vocabulary, the required
sections, and the human-acceptance gate — is `.claude/rules/70-adr.md`, which **strengthens** this
requirement rather than restating it. It is not duplicated here.

*Source: `dotnet.yaml#P-DN-5`, `python.yaml#P-PY-5` · Enforcement: mechanical, structural only
(`.claude/hooks/adr_structure_guard.py`, H5)*

---

## 10.6 What this file does not do

- It does not restate a stack's mechanism for meeting a principle. That is `20-dotnet.md`,
  `21-python.md`, `22-web-typescript.md`, `23-angular.md` or `24-electron.md`.
- It does not define the DB, LangGraph, ADR or functional-record gates. Those are rules 50, 30, 70
  and 90, pointed to from `.claude/rules/00-authority.md` §00.9.
- It does not authorize weakening a test to satisfy a principle. See
  `.claude/rules/40-testing.md` §40.6.

---

## 10.7 Implementation honesty and reference fixtures — H-1, H-2

*Authorized by `docs/adr/0012-principle-ix-reference-fixtures-and-no-fabricated-success.md`
(Accepted). Migrated from the retired Spec Kit constitution §IX clauses 2b and 3, and the
`FR-SCOPE-004`…`FR-SCOPE-007` restatement of clause 3. **That material was migration input. It is
not authority**, and its non-authoritative status under `.claude/rules/00-authority.md` §00.4 is
unchanged by having been read. This file is the authority for `H-1` and `H-2`; the retired
documents are not, and do not become so.*

§10.7 was **appended** rather than inserted, so that every existing section number in this file
stays stable and no cross-reference from another rule breaks. Its rule-id space is **`H-*`**,
deliberately distinct from `P-*` (from `principles.yaml`) and `C-*` (the identically-stated .NET and
Python convention blocks), because its source is an ADR and not a migrated pack.

**Scope: repository-wide.** Both rules apply to every stack — `dotnet/**`, `ragcore/**`,
`integrations/**`, `apps/web/**`, `apps/desktop/**`, and any future stack.

### H-1 — No fabricated, stubbed or silently degraded success

**An operation that did not do the thing asked of it never reports that it did.**

Where a capability is unsupported, unavailable, deferred or not implemented, the outcome is
**explicit and visible at the boundary that returns it** — an escalation, a declared unsupported
outcome, a raised error, or a surface documented as inert that says so in what it returns.

Prohibited specifically:

- **Silent degradation** — quietly doing less than was asked while returning the shape of a full
  success.
- **A stubbed success** — a placeholder, `TODO`, or unimplemented path that returns a success
  value, a success status, or a success-shaped record.
- **A fabricated result** — a synthesized, simulated, sampled or plausible-looking value presented
  as the product of real execution. This **includes a value produced by a model** and returned as
  though it were retrieved, computed, or confirmed by an external system.

**This is not a prohibition on fallback.** A declared fallback, a cached value served as a cached
value, a partial result labelled partial, a documented default, and a retry are all legitimate.
What they have in common is that **the caller can tell what they got**. The rule governs the
honesty of the report, not the ambition of the behaviour.

**How this differs from the principles it sits beside**, so it is not read as a duplicate:

| Rule | Governs | Why it does not cover `H-1` |
|---|---|---|
| **P-8** | building speculative capability | forbids *building* what no requirement needs; says nothing about *fabricating a result* from what was never built |
| **P-11** | invalid input at a boundary | a stubbed success is not invalid input; it is valid input answered dishonestly |
| **P-14** | surprising behaviour | asks for unsurprising behaviour without prohibiting a synthesized success |
| **P-30** | a **caught error** | in the failure `H-1` describes, no error is raised at all — that is what makes it silent |
| **`90-functional-knowledge.md`** | what the **record** may claim | §90.11 states it authorizes nothing about implementation behaviour |

The escalation half of the original clause — that an unsupported capability falls back to manual
resolution or escalation — is **not** restated here. It is owned by **A3 §6.2** (the outcome
vocabulary `{answered_sop, resolved_action, escalated, denied}` and `escalation_reason`), and
`.claude/rules/00-authority.md` §00.5 forbids restating an owned requirement.

*Source: ADR-0012 · Enforcement: **procedural** — no mechanism in this repository detects a stubbed
success or a fabricated result. ADR-0012 does not authorize building one; that is a separate,
human-directed decision (`.claude/rules/40-testing.md` §40.7). A rule whose enforcement is
procedural is not optional — it is reviewed rather than gated.*

### H-2 — Reference fixtures are labelled, inert, production-excluded, and never product

**Reference fixtures are permitted, and are never product.**

Inert reference operations may exist so that governance, consent and approval paths are exercisable
before a real capability is defined. Each one:

1. **Is labelled a reference fixture** — recognisably, and without a catalogue lookup, so it is
   identifiable from a log line, a queue entry or an audit record.
2. **Is inert.** It produces no real effect in any external system, modifies no account, device or
   record, and claims no confirmation the platform could not actually perform. *Inert* means **has
   no external effect**, not *is not wired up yet*.
3. **Is excluded from production configuration**, and the exclusion is **enforced rather than
   documented**. A runbook step saying somebody should not install them does not satisfy this.
4. **Is never presented to any user as a product capability**, and is never counted as, substituted
   for, or allowed to become a real defined capability.

**A fixture is not a capability waiting to be finished.** Promoting one is a deliberate act that
replaces it with a real capability under whatever gate that capability needs — never a relabelling.

**The boundary this respects.** An enforced production exclusion decides whether fixture rows are
*installed*; it never decides what a row *means*. No treatment, role or entitlement may vary by
environment — a control that behaves differently in production is a control nobody has exercised.
"Exclude the fixtures in production" is one careless step away from "relax the gate in
development", and they are not the same rule.

*Source: ADR-0012 · Enforcement: **mechanical for the fixtures that exist today** —
`ragcore/tests/governance/test_fixtures_excluded.py` asserts all four properties against
`ragcore/src/ragcore/governance/fixtures.py`, and separately asserts that the exclusion has not
become an environment branch. `H-2` is written repository-wide deliberately; only `ragcore` has
fixtures today, so only `ragcore` has a check. A fixture introduced on any other stack owes the same
four properties and would need its own.*
