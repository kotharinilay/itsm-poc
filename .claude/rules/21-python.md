---
paths:
  - "ragcore/**"
  - "integrations/**"
---
# 21 — Python engineering rules

## Scope

**This file governs Python code only.**

| Governs | Does not govern |
|---|---|
| `ragcore/**` — `src/`, `workers/`, `tests/`, `migrations/` | `dotnet/**` (`.claude/rules/20-dotnet.md`) |
| `integrations/**` — `src/`, `workers/`, `tests/` | `apps/web/**`, `apps/desktop/**` (`.claude/rules/22-web-typescript.md`, `.claude/rules/23-angular.md`, `.claude/rules/24-electron.md`) |
| `ragcore/pyproject.toml`, `integrations/pyproject.toml` and their lockfiles | `build/docker/**`, `.github/workflows/**` (`.claude/rules/80-security-ops.md`) |

**Nothing in this file is evidence of a .NET, TypeScript,
Angular or Electron requirement**, and no rule here may be carried to another stack by analogy
(`.claude/rules/00-authority.md` §00.5).

Repository-wide principles in `.claude/rules/10-principles.md` apply to Python **in addition** to
everything here. This file states the Python mechanism; it never relaxes the principle.

**The LangGraph implementation is Python, and this file applies to it — but a change to graph
behavior is governed by `.claude/rules/30-langgraph.md` first, in full.** Style conformance never
licenses a topology, state or authority change.

**Origin** lines record what each rule was migrated from. They are provenance, never a citation of
authority (`.claude/rules/00-authority.md` §00.3).

**Enforcement** vocabulary: `mechanical` | `partial` | `procedural` | `currently-unenforced`.
Verified against `ragcore/pyproject.toml`, `integrations/pyproject.toml`,
`.github/workflows/ragcore.yml` and `.github/workflows/integrations.yml`.

---

## 21.1 Platform baseline and toolchain

### Baseline
**The Python baseline is `py312`** — `requires-python >= 3.12`.
*Origin: `python#baseline` · Enforcement: mechanical — both projects declare
`requires-python = ">=3.12,<3.13"` and `target-version = "py312"`*

### Toolchain
These six entries carried no identifier of their own in the retired input; the identifiers below
are this file's.

| Origin | Requirement | Emitted to | Enforcement |
|---|---|---|---|
| `python#toolchain.linter` | Ruff. `[tool.ruff.lint] select` is written **explicitly** — the Ruff default is only `[E4, E7, E9, F]`, so the set must be stated | `pyproject.toml` | mechanical |
| `python#toolchain.formatter` | `ruff format`, `quote-style = "double"` | `pyproject.toml` | mechanical (see note) |
| `python#toolchain.import_sort` | Ruff `I` (isort), enabled by inclusion in `select`. **No standalone isort.** | `pyproject.toml` | mechanical |
| `python#toolchain.type_checker` | `mypy --strict` **or** `pyright` (`typeCheckingMode = "strict"`), run as a **CI gate** | `pyproject.toml` | mechanical |
| `python#toolchain.security` | Ruff `S` (flake8-bandit). **No separate Bandit run needed.** | `pyproject.toml` | mechanical |
| `python#toolchain.packaging` | PEP 621 `[project]` metadata in `pyproject.toml`, plus a **committed pinned lockfile** (`uv.lock` \| `poetry.lock` \| `requirements*.txt`) | `pyproject.toml` | mechanical — both projects use `uv` and commit `uv.lock` |

> **Note on `quote-style`.** Neither `pyproject.toml` writes `quote-style` explicitly. The Ruff
> formatter's default *is* `double`, so the required behavior holds and `ruff format --check` gates
> it. The setting is nonetheless not written where this rule says to emit it — registered as
> **DV-8** (cosmetic) in `docs/governance/open-items.md` §1.

### The three strictness switches

| # | Origin | Switch | Realizes | Enforcement |
|---|---|---|---|---|
| **S1** | `python#P-PY-S1` | `[tool.mypy] strict = true` (or pyright strict) | PY-3 | mechanical — both projects set `strict = true` and add `warn_unreachable`, `warn_no_return`, `disallow_any_unimported`, `disallow_untyped_defs`, `no_implicit_reexport` |
| **S2** | `python#P-PY-S2` | `[tool.ruff.lint] select` includes `S, ASYNC, B, DTZ, PTH` (+ `E, F, I, UP, SIM`) | PY-22 | mechanical |
| **S3** | `python#P-PY-S3` | `ruff check` **and** `ruff format --check` run as **failing CI steps** | — | mechanical |

`strict = true` turns on `disallow-untyped-defs`, `disallow-untyped-calls`,
`disallow-incomplete-defs`, `check-untyped-defs`, `warn-return-any`, `strict-equality`,
`no-implicit-reexport` and `warn-unused-ignores`. Pyright `strict` is the equivalent set.

*Origin: the three strictness entries of the retired Python pack, identified in the table above.*

### PY-22 — Ruff is adopted with an explicit selected set and runs in CI
Configure Ruff once in `pyproject.toml` with an explicit `select` set and run `ruff check` and
`ruff format --check` in CI, replacing flake8/isort/black/bandit. **This is the switch that makes
every other PY rule a build-failing gate.**
*Origin: `lang/python#PY22` · core · Enforcement: mechanical*

### Suppression policy
**No auto-suppress. A violation fails CI.** Suppression is only a **justified `# noqa: <code>` on
the specific line**, with the reason after the code. **Never a blanket ignore.**

Both projects commit `ignore = []` and state it stays that way. Adding to `ignore` or to
`per-file-ignores` is a baseline change requiring an ADR (`.claude/rules/70-adr.md` §70.2 B(2)).

*Origin: `python#P-PY-S3` · Enforcement: mechanical for `ruff check` failing CI; the
*justification text* on a `# noqa` is review*

> **Sanctioned per-file-ignore.** `"tests/**/*.py" = ["S101"]` is the source's own mechanism for
> PY-6 (assert permitted in tests, banned elsewhere) — a split, not a relaxation.
>
> **Deviation DV-9, open.** `ragcore/pyproject.toml` additionally carries
> `"migrations/versions/*.py" = ["N999", "E501"]`. Alembic-generated revision module names are the
> stated reason. It is a `per-file-ignores` entry beyond what the source sanctions, predating this
> migration. Recorded; **not** removed under this phase.

### Selected rule set — as committed
```toml
select = ["E", "F", "B", "I", "UP", "S", "PTH", "SIM", "ASYNC", "DTZ", "N"]
```
`N` (pep8-naming) is **beyond** the baseline set. The source explicitly contemplates it: P-PY-1 says
`N` "is NOT in the base selected set and must be ADDED to select to make naming mechanical".
Adding it is a **strengthening**, and it makes PY-1 mechanical. Recorded as such, not as a
deviation.

`T20` (flake8-print) is **not** selected — see PY-4.

---

## 21.2 Typing

### PY-3 — Public surface is annotated; the type checker gates the build in strict mode
Annotate every public parameter and return (`def total(items: list[Order]) -> Money:`), and run the
type checker in **strict mode** so untyped or partially-typed public surface fails the build. Prefer
precise types (`X | None`, `Literal[...]`, `TypedDict`) over `Any`.
*Origin: `lang/python#PY3` · satisfies `principles#P20` · Enforcement: mechanical — `mypy --strict`
is a failing CI step in both workflows*

### PY-21 / P-PY-3 — Modern generic and union syntax (PEP 585 / PEP 604)
Annotate with `list[int]`, `dict[str, int]` and `X | None` rather than `typing.List`, `typing.Dict`
or `Optional[X]`. Add `from __future__ import annotations` where a target runtime predates the
syntax.
*Origin: `lang/python#PY21`, `python#P-PY-3` · Enforcement: mechanical — Ruff `UP006`,
`UP007`/`UP045`, `UP035`*

---

## 21.3 Correctness and likely-bug bans

### PY-1 — No mutable default arguments
Write `def f(items: list[int] | None = None): items = items or []` — take `None` as the default and
build the mutable value inside the body. **Never `def f(items=[])` / `def f(x=dict())`**: the
default is evaluated once at definition time and shared across every call, so state leaks between
invocations.
*Origin: `lang/python#PY1` · core · satisfies `principles#P25` · Enforcement: mechanical — Ruff
`B006`, `B008`*

### PY-13 — The `B` (flake8-bugbear) family is enabled
Keep `B` in the Ruff selected set so bugbear idioms (mutable defaults, `assert` tuples, useless
comparisons, missing `raise ... from`) are caught. This rule guarantees the **family is switched
on**; the individual bans are PY-1 and PY-14.
*Origin: `lang/python#PY13` · Enforcement: mechanical — `B` is in `select` in both projects*

### PY-12 — No unused imports/variables, no undefined names
Ship no unused import, no unused local, and no reference to an undefined name. **Remove dead code
rather than leaving it "just in case."**
*Origin: `lang/python#PY12` · core · satisfies `principles#P8` · Enforcement: mechanical — Ruff
`F401`, `F841`, `F821`*

### PY-20 — `is` / `is not` for `None`
Test identity for the `None` singleton: `if value is None:` / `if value is not None:`. Do not write
`value == None` — equality invokes `__eq__`, which a type may override with surprising results.
*Origin: `lang/python#PY20` · Enforcement: mechanical — Ruff `E711`*

### PY-24 — Timezone-aware datetimes only
Build aware timestamps: `datetime.now(tz=timezone.utc)`, `datetime.fromtimestamp(ts, tz=timezone.utc)`.
**Never `datetime.now()`, `datetime.utcnow()` or `datetime.today()`** — naive datetimes silently
bind to machine-local time and compare and serialize incorrectly across environments.
*Origin: `lang/python#PY24` · Enforcement: mechanical — Ruff `DTZ` family (`DTZ005`, `DTZ003`,
`DTZ002`)*

### PY-7 — `pathlib.Path` over `os.path`
Build and manipulate paths with `pathlib.Path` (`Path(base) / "sub" / name`, `path.read_text()`,
`path.exists()`) instead of `os.path.join` / `os.path.exists` / `open(str_path)`. Object paths are
cross-platform and composable.
*Origin: `lang/python#PY7` · Enforcement: mechanical — Ruff `PTH` family (`PTH118`, `PTH123`)*

---

## 21.4 Errors and resources

### PY-2 — No bare `except`
Catch the narrowest exception you can act on (`except KeyError:`). A deliberate `except Exception:`
is allowed **only** at a boundary that logs and re-raises. **Never `except:` (bare)** — it also
swallows `KeyboardInterrupt`/`SystemExit` and hides real bugs.
*Origin: `lang/python#PY2` · core · satisfies `anti-patterns#A15`, `principles#P30` · Enforcement:
mechanical — Ruff `E722`*

### PY-14 — `raise ... from` when translating
When translating an exception, chain the cause: `raise DomainError("...") from exc`. Use bare
`raise` to rethrow unchanged. Suppress a cause deliberately with `from None`. **Never raise a new
exception inside an `except` without `from`** — that loses the original traceback and causality.
*Origin: `lang/python#PY14` · core · satisfies `anti-patterns#A30`, `principles#P30` · Enforcement:
mechanical — Ruff `B904`*

### PY-6 — `assert` is not runtime validation
Validate with an explicit raise (`if qty < 0: raise ValueError("qty must be >= 0")`). **Never rely
on `assert` for a runtime check** — the interpreter strips every `assert` under `-O` /
`PYTHONOPTIMIZE`, so the check silently disappears in production. **Asserts inside tests are fine**,
which is what the `tests/**` per-file-ignore of `S101` implements.
*Origin: `lang/python#PY6` · core · Enforcement: mechanical — Ruff `S101`, with the test-path split*

### PY-9 — Every resource is acquired in a context manager
Acquire every resource in a `with` block (`with open(path) as f:`, `with lock:`,
`async with pool.acquire() as conn:`) so it is released on the normal and exception paths. **Do not
hold a bare `open()` handle you must remember to `.close()`.**
*Origin: `lang/python#PY9` · satisfies `principles#P31` · Enforcement: mechanical — Ruff `SIM115`*

---

## 21.5 Async

### PY-23 — No blocking calls inside an `async` function
Inside `async def`, use the awaitable form: `await asyncio.sleep(n)`, an async HTTP client
(`await client.get(...)`), `asyncio.create_subprocess_exec`, or offload genuinely blocking work with
`await loop.run_in_executor(...)`. **Never call `time.sleep`, `requests.get`, blocking `open` or
`input` on the event-loop thread.**
*Origin: `lang/python#PY23` · core · satisfies `performance#PF1`, `anti-patterns#A31` ·
Enforcement: mechanical — Ruff `ASYNC251`, `ASYNC210`, `ASYNC230`, `ASYNC22x`*

---

## 21.6 Security

### PY-8 — No `eval` / `exec` on untrusted input
**Never pass request or user data to `eval()` or `exec()`** — that is arbitrary code execution.
Parse with a typed, data-only mechanism instead: `json.loads`, `ast.literal_eval` for literals, or an
explicit dispatch table for "commands".
*Origin: `lang/python#PY8` · core · satisfies `secure-coding#SC6` · Enforcement: mechanical — Ruff
`S307`, `S102`*

### PY-10 — `subprocess` takes an argument list, never `shell=True` on untrusted input
Invoke external processes with an argument list and no shell —
`subprocess.run(["git", "clone", url], check=True)`. **Never
`subprocess.run(f"git clone {url}", shell=True)`**: a shell string built from input is command
injection. Use the full executable path where feasible.
*Origin: `lang/python#PY10` · core · satisfies `secure-coding#SC3` · Enforcement: mechanical — Ruff
`S602`, `S603`, `S607`*

### PY-25 — Parameterize SQL
Pass values as bound parameters: `cur.execute("SELECT * FROM t WHERE id = %s", (id,))`, SQLAlchemy
`text("... :id").bindparams(id=id)`, or the ORM query API. **Never `f"SELECT ... {id}"` or
`"..." + id` into the query text** — that is SQL injection.
*Origin: `lang/python#PY25` · core · satisfies `secure-coding#SC4`, `anti-patterns#A25` ·
Enforcement: mechanical — Ruff `S608`. The source notes `S608` is a **string-shape heuristic, not
full taint dataflow**, so the rule is broader than its gate.*

### PY-16 — No unsafe deserialization of untrusted data
Parse untrusted input only with data-only loaders bound to explicit types: `json.loads`,
`yaml.safe_load`, or a schema library. **Never `pickle.loads`, `marshal.loads`, or
`yaml.load(..., Loader=yaml.Loader)` on data you did not produce** — each can instantiate arbitrary
objects (RCE).
*Origin: `lang/python#PY16` · core · satisfies `secure-coding#SC6` · Enforcement: mechanical — Ruff
`S301`, `S302`, `S506`*

### PY-15 — No literal credentials in source
Read every secret from the environment or a secret store (`os.environ["DB_PASSWORD"]`, a settings
object bound at startup). **Never assign a credential literal** (`PASSWORD = "hunter2"`,
`connect(password="hunter2")`) in code or in defaults.
*Origin: `lang/python#PY15` · core · satisfies `anti-patterns#A24`, `secure-coding#SC18`,
`principles#P27` · Enforcement: mechanical — Ruff `S105`, `S106`, `S107`*

### PY-18 — No weak hash algorithms in security contexts
Use `hashlib.sha256`/`sha512` for digests and a memory-hard KDF (`argon2`, `bcrypt`,
`hashlib.scrypt`, or `pbkdf2_hmac`) for passwords. **Never MD5/SHA1 for anything security-relevant**;
if a legacy digest is needed for a non-security checksum, mark it `usedforsecurity=False`.
*Origin: `lang/python#PY18` · core · satisfies `secure-coding#SC22` · Enforcement: mechanical — Ruff
`S324`*

### PY-17 — Every outbound HTTP call has an explicit timeout
Pass an explicit finite `timeout=` to every HTTP call (`requests.get(url, timeout=5)`,
`httpx.get(url, timeout=5)`), or configure it once on a shared client/session. **A call with no
timeout can hang indefinitely and exhaust workers and connections.**
*Origin: `lang/python#PY17` · core · satisfies `performance#PF6` · Enforcement: mechanical — Ruff
`S113`*

### PY-19 — No insecure temporary files
Create temp files with `tempfile.NamedTemporaryFile()` / `tempfile.mkstemp()`, which open atomically
with safe permissions. **Never `tempfile.mktemp()`** (returns a name; races between check and open —
TOCTOU) **or a hardcoded `/tmp/...` path.**
*Origin: `lang/python#PY19` · Enforcement: mechanical — Ruff `S306`, `S108`*

---

## 21.7 Logging and style

### PY-4 — Use `logging`; `print` is banned
Obtain `logger = logging.getLogger(__name__)` and emit structured events
(`logger.info("order %s placed", order_id)`). **Reserve `print` for a genuine CLI entrypoint only**,
so levels, handlers and formatting stay configurable.
*Origin: `lang/python#PY4` · satisfies `principles#P29` · Enforcement: **currently-unenforced***
> **Deviation DV-10, open.** The source's mechanism is Ruff `T201` (flake8-print, family `T20`), and
> the source states plainly that `T20` is **not** in the baseline selected set and **must be added
> to `select`** for the rule to fire. Neither `ragcore/pyproject.toml` nor
> `integrations/pyproject.toml` selects `T20`, so the ban is **unguarded in both directions**.
> This is recorded and the configuration is **not** changed
> (`.claude/rules/00-authority.md` §00.7; `docs/governance/open-items.md` §1). The rule is binding regardless: do not write `print` in
> application or library code. Adding `T20` to `select` would be a baseline-realizing configuration
> change and is a human decision.

### PY-5 — f-strings over `%` and `str.format`
Use `f"total={total}"`. **Keep `%`-style only inside logging calls**
(`logger.info("total=%s", total)`), where lazy interpolation matters.
*Origin: `lang/python#PY5` · Enforcement: mechanical — Ruff `UP032`, `UP031`*

### PY-11 / P-PY-1 — PEP 8 layout and naming
Let `ruff format` (Black-compatible) own layout and `ruff check` own the pycodestyle rules; **do not
hand-format**. Naming: **snake_case** modules and functions, **PascalCase** classes, PEP 8
throughout.
*Origin: `lang/python#PY11`, `python#P-PY-1` · Enforcement: mechanical — Ruff `E` family and
`ruff format --check` for layout; `N` (pep8-naming: `N801`, `N802`, `N806`) for naming, **selected
in both projects**, which is the strengthening the source describes*

---

## 21.8 Tests

Python test layout and naming is in `.claude/rules/40-testing.md` §40.3. It
is not duplicated here.

---

## 21.9 Deliberate non-equivalences

The following .NET baseline rules have **no Python counterpart in any authoritative source**, and
none is invented here (`.claude/rules/00-authority.md` §00.5):

- `EF Core 10 + Npgsql` (`BL-09`) and `AsNoTracking`/compiled queries (`BL-14`) — .NET
  data-access rules. Python persistence in this repository is SQLAlchemy + Alembic, governed by
  `.claude/rules/50-database.md`, **not** by a translated EF rule.
- `IExceptionHandler` → `ProblemDetails` (`BL-19`) — a .NET implementation rule. Both Python
  services emit problem-details-shaped errors; that is **existing implementation, not baseline
  authority**.
- Constructor injection with `Microsoft.Extensions.DependencyInjection` (`BL-02`) — a .NET container
  rule. The language-independent obligation is `principles#P26`
  (`.claude/rules/10-principles.md` P-26), which applies to Python directly and needs no .NET
  translation.
- Minimal APIs, URI-segment versioning, `IHttpClientFactory` typed clients, `DelegatingHandler`
  chains, Polly resilience, `MapHealthChecks` (`BL-04`, `BL-05`, `BL-25`, `BL-28`, `BL-31`,
  `BL-32`) — .NET framework mechanisms.

> **`BL-10` is deliberately not on this list.** It is a **repository- and deployment-level**
> requirement — one versioned migration mechanism, executed as a gated job in CI/deploy, never at
> application startup — and it applies to `ragcore/**` **directly**, because Alembic under
> `ragcore/migrations/` is that mechanism. It is not a translated EF rule, and the procedure for it
> is `.claude/rules/50-database.md`, in full.

> **Eight places in this tree state a requirement whose only baseline statement is on the .NET
> stack** — middleware ordering (BL-26), internal exception detail (BL-18), readiness independence
> (BL-25), unmanaged HTTP clients (BL-32) and the generic-repository ban (BL-14). They are
> registered as an open gap in `docs/governance/open-items.md` §5, decision **UD-8**. **Do not
> close the gap by inventing a Python rule here** — that is an engineering-baseline change and
> needs an ADR (`.claude/rules/70-adr.md` §70.2 B(6)).

Where an equivalent obligation genuinely exists it is stated as the **repository-wide principle** in
`.claude/rules/10-principles.md` and applies to Python from there — not as a copy of the .NET rule.
