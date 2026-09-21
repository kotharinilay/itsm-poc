# CI/CD — Azure DevOps pipelines

One pipeline per concern, matching the gates `.claude/rules/40-testing.md` §40.6 lists. Each file
opens with what it asserts and why, in the same terms as the rule that requires it.

**A pipeline is where a gate runs. It is not authority.** The rule that requires a gate is in
`.claude/rules/**`, and a passing pipeline is never evidence that a rule is met
(`.claude/rules/00-authority.md` §00.4).

## The pipelines

| File | Asserts | Triggered by |
|---|---|---|
| `dotnet.yml` | restore, build with `-warnaserror`, `dotnet format --verify-no-changes`, every suite under `dotnet/tests/` | `dotnet/**` |
| `ragcore.yml` | Ruff lint, Ruff format, `mypy --strict`, pytest | `ragcore/**` |
| `integrations.yml` | the same four gates from a separate lock and environment, plus the cross-deployable boundary | `integrations/**` |
| `web.yml` | ESLint, Prettier, `tsc -b`, build, unit tests, the WCAG 2.2 AA sweep, the CSP check | `apps/web/**` |
| `desktop.yml` | typecheck, lint, the Electron security suite, **and the meta-guard proving that suite fails when a switch is flipped**, then build | `apps/desktop/**`, `apps/web/projects/desktop-renderer/**` |
| `migrations.yml` | single head, upgrade from base, models match DDL, **every** downgrade, against a real PostgreSQL; then the non-integration suite | `ragcore/migrations/**`, `ragcore/src/ragcore/persistence/**` |
| `contracts.yml` | emission from the running services, determinism, publishability, no unapproved breaking change, no stale committed contract; publishes the versioned artifacts | the API surfaces and the contract tooling |
| `boundaries.yml` | no cross-deployable dependency, **and** that the boundary and architecture guards still fail on a planted violation | every pull request, unconditionally |
| `edge.yml` | all traffic traverses the edge, and the shared edge-trust policy agrees across APIM, Front Door, both ingress manifests and both stacks | every pull request, unconditionally |
| `images.yml` | every image is built, **started and inspected** | `build/docker/**` and every tree that goes into an image |
| `security.yml` | Gitleaks over history; .NET, web and desktop dependency audits | every pull request, plus a weekly schedule |
| `governance.yml` | the governance guard suite — the gates are wired, the rules are well formed, the ADR index is consistent | `.claude/**`, `CLAUDE.md`, `docs/adr/**`, `docs/governance/**` |
| `base-image-digests.yml` | resolves and re-pins the three base-image digests, scans all three families, publishes the diff | monthly schedule, or manually with a reason |

`templates/use-uv.yml` installs uv and syncs **one** deployable from **its own** lockfile;
`templates/python-gates.yml` runs the four Python gates. A pipeline that needs both Python
environments calls the first template twice — the two services share no package by design
(ADR-0007), and syncing one and using it for both would test against a dependency set that does
not ship.

## Which pipelines must be required

These are the build-validation policies to configure on the default branch. **The set matches what
the GitHub surface marked required**, so no gate loses its blocking status in the move.

| Pipeline | Policy | Why |
|---|---|---|
| `boundaries` | required, **no path filter** | the violation it catches can be introduced from any tree, and no compiler sees it |
| `edge` | required, **no path filter** | most of the edge boundary lives in files no compiler reads, and opening it is a one-word change that reviews as formatting |
| `security` | required, **no path filter** | a secret can be committed from any tree |
| `governance` | required, path-filtered to the governance surface | a change to the gates must re-prove the gates |
| `dotnet`, `ragcore`, `integrations`, `web`, `desktop` | required, path-filtered to their stack | each is that stack's whole quality gate |
| `migrations` | required, path-filtered to the schema | a schema change that breaks a downgrade must not merge |
| `contracts` | required, path-filtered to the API surface | a route whose emitted shape drifts from its contract must not merge |
| `images` | required, path-filtered | an image that cannot start must not merge |
| `base-image-digests` | **not** a build validation | it is scheduled, and its output is reviewed as an ordinary pull request |

**Optional build validation is not build validation.** Set each policy to required, not optional,
or the gate becomes advice.

## Branch policy

> **Verified 2026-09-22: `main` on the GitHub remote has NO branch protection.** The API returns
> *Branch not protected*, so no required status check is enforced today and a direct push to `main`
> is possible. The policy below is therefore **the target state, not a description of the current
> one**, and there is no existing enforcement for an Azure DevOps policy to be made equivalent to.
> Registered as **UD-12** in `docs/governance/open-items.md`.

The target state on the default branch:

- **No direct pushes.** Every change arrives by pull request.
- **Build validation** for each pipeline above, required, with the stated path filter.
- **Linear history** is not required and is not assumed; nothing in the gates depends on it.

The repository is hosted on **GitHub** (`kotharinilay/itsm-poc`) and **no Azure DevOps
organisation or project is connected to it**. Nothing here runs until one exists. If the repository
stays on GitHub while Azure DevOps runs the pipelines, wire the Azure DevOps GitHub service
connection and keep GitHub branch protection as the mechanism that enforces the checks. If it moves to Azure Repos, the equivalent is a branch policy per pipeline. **Either way
the required set above is the same**, and the move is not an occasion to drop one.

## Before deleting `.github/`

`PARITY.md` states the criteria, the mapping and the current status. **Do not delete
`.github/workflows/**` before every criterion there is met.** Until then it remains the
authoritative execution surface and both surfaces exist deliberately.
