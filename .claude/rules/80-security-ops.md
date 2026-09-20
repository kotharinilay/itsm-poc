# 80 — Security and operational engineering

**Scope: repository-wide**, covering every stack and the build, image and deployment surface —
`build/docker/**`, `build/scripts/**`, `.github/workflows/**`, and the security-relevant behavior of
`dotnet/**`, `ragcore/**`, `integrations/**`, `apps/web/**` and `apps/desktop/**`.

This file owns **repository-wide security and operational policy**. The per-language security *rules*
live with their stack — `.claude/rules/20-dotnet.md` §20.10 (crypto, TLS) and
`.claude/rules/21-python.md` §21.6 (the Ruff `S` bans) — and are not duplicated here. This file
states what applies across all of them and what governs the runtime.

**Enforcement** vocabulary: `mechanical` | `partial` | `procedural` | `currently-unenforced`,
verified against the committed workflows and Dockerfiles.

---

## 80.1 Security is not a separate concern from the gates

The database is part of the **authorization boundary**, not a persistence detail
(`.claude/rules/50-database.md` §50.1). Execution authority in the graph is architectural
(`.claude/rules/30-langgraph.md` §30.3). Neither is restated here, and **nothing in this file may be
read as relaxing either**. A security improvement that moves an invariant out of the database into
application code is an architecture change requiring an ADR, not a hardening tweak
(`.claude/rules/70-adr.md` §70.2 D(3)).

## 80.2 Least privilege, operationally

`principles#P17` is stated once, repository-wide, in `.claude/rules/10-principles.md` P-17. It is
**not** re-stated here. What this section adds is where it bites operationally, because Phase 7
found the principle had survived only as one database instance
(`docs/migration/phase-7-validation.md` §4.4) and that narrowing is now corrected.

P-17 governs, at minimum:

| Surface | What "minimum rights" means there | Enforcement |
|---|---|---|
| Code visibility (every stack) | most restrictive access modifier that works; `sealed`/`final` unless designed for extension | partial (`.claude/rules/20-dotnet.md` DN-11, DN-12) |
| Database principals | the migration job holds DDL; the runtime holds DML/SELECT only | mechanical (`ragcore/migrations/versions/0019_database_principals.py`) |
| Managed identity / Azure RBAC | the narrowest resource and action set; no wildcard role for convenience | partial (`AzureIdentityTests`) |
| Key Vault access policies | per-workload, per-secret scope | procedural |
| Service Bus | send/listen rights scoped per queue or topic, never namespace-wide | procedural |
| Container runtime | non-root, no added capabilities, read-only root filesystem where feasible | partial (§80.5) |
| CI tokens | least-scoped `GITHUB_TOKEN` permissions per workflow | procedural |
| Browser / renderer (`apps/web`, `apps/desktop`) | context isolation, minimal preload surface, minimal token scope | partial (the Electron security suite; `.claude/rules/22-web-typescript.md` §22.3) |

**Never grant broad or wildcard rights for convenience** — that is the rule, and it is the same rule
in every row.

## 80.3 Secrets

### BL-15 — Secrets management
**Secrets live in Azure Key Vault and reach the application as Key Vault references resolved via
managed identity.**
*Source: `BL-15` · Enforcement: partial (`AzureIdentityTests`; Gitleaks in
`.github/workflows/security.yml`)*

### Repository-wide secret handling
Following from `principles#P27` (`.claude/rules/10-principles.md` P-27), across every stack:

- **No secret in source.** No credential, API key, connection string or token literal — including in
  defaults, test fixtures, sample configs or comments.
- **No secret in an image**, in a build argument, or in a committed settings file.
- **No secret in a log.** Correlation ids and tenant ids are loggable; credentials and tokens are
  not (`.claude/rules/20-dotnet.md` BL-24 limits OTel baggage to an explicit allowlist for the same
  reason).
- **The same build artifact runs in every environment**, with only its configuration changing
  (P-27). A per-environment build is a defect, not a deployment strategy.
- Configuration reaches the app through the layering in `.claude/rules/20-dotnet.md` BL-16, with
  secret material arriving last, through the same env-var channel.

*Enforcement: mechanical for literal credentials in Python (`.claude/rules/21-python.md` PY-15, Ruff
`S105`/`S106`/`S107`) and repository-wide via **Gitleaks** in `.github/workflows/security.yml`;
**currently-unenforced** for credential literals in C# — no BannedApi or analyzer binding covers
them (recorded as part of **EG-2**).*

## 80.4 Dependency and supply-chain hygiene

| Control | Requirement | Enforcement |
|---|---|---|
| Pinned dependencies | A committed pinned lockfile per project — `uv.lock` (RagCore, Integrations), `package-lock.json` (web, desktop), central package management for .NET | mechanical (`python.yaml#toolchain.packaging`; `dotnet.yaml#toolchain.packages` with `ManagePackageVersionsCentrally` **and** `CentralPackageTransitivePinningEnabled`) |
| Vulnerable packages | `dotnet list package --vulnerable --include-transitive` | mechanical (`security.yml`) |
| npm advisories | `npm audit --audit-level=high` for web and desktop | mechanical (`security.yml`) |
| Secret scanning | Gitleaks over the repository | mechanical (`security.yml`) |
| Base-image CVEs | resolved base images are scanned when digests are re-pinned | mechanical (`base-image-digests.yml`) |

Python dependency-vulnerability auditing has **no equivalent step** in `security.yml`. Recorded as
enforcement gap **EG-6**; not implemented in this phase (Phase 9 brief §24).

## 80.5 Container build and runtime

### BL-39 — Dockerfile structure and base-image hardening
**Locked convention.** Production images use the **minimal, shell-less, package-manager-free Ubuntu
chiseled base for .NET 10** — `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled` — **pinned by
digest in the pipeline, never a floating tag.** The build is **multi-stage**: the SDK image builds,
the chiseled runtime image runs.

Hard rules, as the source states them:

1. **Non-root user by default** — `app`, **UID 1654**. *"do not override to root."*
2. **Shell-less / no package manager in the final image** (chiseled) — shrinks CVE surface.
3. **Pin the base by digest**, not `latest` and not a floating major tag.
4. **Read-only root filesystem where feasible.**
5. **Document the base-image policy in-repo** — which family, why chiseled, how digests are bumped.

*Source: `BL-39` · Enforcement: partial·mechanical — `build/docker/dotnet.Dockerfile` uses the
chiseled base, builds multi-stage from `mcr.microsoft.com/dotnet/sdk:10.0-noble`, sets `USER 1654`,
and pins via a `@sha256:` `RUNTIME_BASE` build arg that `.github/workflows/base-image-digests.yml`
resolves and re-pins with `crane`. `.github/workflows/images.yml` builds, starts and inspects every
image (`build/scripts/smoke-images.sh`). Requirement 5 is satisfied by the in-file policy comments
and this section.*

> The Python and portal images use `python:3.12-slim-bookworm` and `node:22-bookworm-slim`, also
> digest-pinned and non-root (`USER 10001` / `10002` / `10004`). **`chiseled` is a .NET image family
> and has no Python or Node equivalent**, so requirements 1–5 apply to those images in substance
> (minimal base, non-root, digest-pinned) but not as the same literal tag. This is stated in
> `build/docker/ragcore.Dockerfile` and is not a deviation from `BL-39`, which scopes the chiseled
> requirement to .NET.

### BL-38 — Build mode
**`.NET SDK container publish.**
*Source: `BL-38` · Enforcement: **deviation DV-11, open.** The repository builds the .NET image with
a hand-written multi-stage `build/docker/dotnet.Dockerfile` rather than `dotnet publish
/t:PublishContainer`. The Dockerfile states the reason inline: SDK images are not produced for
chiseled variants, so the only way to reach a chiseled runtime is to build elsewhere and copy the
output in. `BL-39` itself refers to the SDK-publish path ("the D13.3 SDK-publish path") as setting
the hardening properties *by construction*, which the hand-written Dockerfile instead sets
explicitly. **Recorded, not repaired.** Reconciling `BL-38` with `BL-39`'s chiseled requirement is a
human decision.*

### BL-37 — Container runtime configuration
**HTTP probes + explicit resource limits + a 25-second drain.**

- Probes are **HTTP**, against the endpoints in `.claude/rules/20-dotnet.md` BL-25 —
  `/health/live` for liveness and `/health/ready` for readiness.
- **Explicit CPU and memory limits** on every container.
- **A 25-second termination drain**, so in-flight requests complete on scale-in. This is why
  `CancellationToken` propagation (`BL-23`) is a hard rule rather than a nicety.

*Source: `BL-37` · Enforcement: partial — the .NET image deliberately carries **no `HEALTHCHECK`
instruction**; probes are declared in `build/docker/containerapps/monolith.yaml`, which is where
limits and the drain period are configured. `.github/workflows/images.yml` starts and inspects each
image.*

### BL-34 — Transport / broker
**Azure Service Bus Standard.** Platform topology — which deployables exist and which hops they
meet on — is owned by **A2**, not by this file.
*Source: `BL-34` · Enforcement: procedural*

### BL-30 (runtime half) — Singletons via Container Apps Jobs
**Work that must run exactly once runs as a Container Apps Job. No distributed lock.** The
application half of this rule is `.claude/rules/20-dotnet.md` BL-30.
*Source: `BL-30` · Enforcement: procedural*

## 80.6 Deployment ordering

**Migrations run as a gated job *before* revision activation, never at application startup**
(`.claude/rules/50-database.md` §50.7, `.github/workflows/migrations.yml`). A consequence that
belongs here: **a migration must be backward-compatible with the currently deployed application
revision**, because the old revision is still serving when the migration runs. That compatibility
statement is mandatory content of every DB change description
(`.claude/rules/50-database.md` §50.4 item 10).

**Do not move DDL to application startup** — it contradicts the stated architecture and requires an
ADR, not merely approval (`.claude/rules/50-database.md` §50.6).

## 80.7 What this file does not do

- It does not restate the per-language security rules. Those are
  `.claude/rules/20-dotnet.md` §20.10 and `.claude/rules/21-python.md` §21.6.
- It does not restate `principles#P17`. That is `.claude/rules/10-principles.md` P-17.
- It does not define the database authorization boundary or the graph execution-authority
  protections. Those are `.claude/rules/50-database.md` and `.claude/rules/30-langgraph.md`.
- It does not authorize adding a scanner, analyzer or CI step to close a gap it records. That is a
  separate, human-directed decision (Phase 9 brief §24).
- It does not treat a passing security workflow as evidence that a rule is met
  (`.claude/rules/00-authority.md` §00.4).
