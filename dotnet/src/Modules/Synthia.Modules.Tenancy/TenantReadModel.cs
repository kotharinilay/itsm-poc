using System.Collections.Frozen;
using Microsoft.EntityFrameworkCore;
using Synthia.Contracts.Paging;
using Synthia.Contracts.Querying;
using Synthia.Contracts.ReadModels;
using Synthia.Persistence;
using Synthia.Persistence.Paging;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Identity;

namespace Synthia.Modules.Tenancy;

/// <summary>The administrator read surface over the organisation registry.</summary>
/// <remarks>
/// Status and identifiers only. <b>No secret material reaches this surface</b> — not values, not
/// Key Vault references (contracts §read-views rule 2). <c>tenant_entitlement</c>, which carries
/// credential references, has no published view for exactly that reason.
/// </remarks>
public interface ITenantReadModel
{
    /// <summary>Lists organisations.</summary>
    /// <param name="filter">Typed narrowing over the whitelisted fields.</param>
    /// <param name="request">The validated page request.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page of organisations.</returns>
    Task<KeysetPage<TenantView>> ListAsync(
        TenantRegistryFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken);
}

/// <summary>The administrator read surface over the platform dashboard.</summary>
/// <remarks>
/// <b>Aggregated and derived figures MUST NOT reveal any single organisation's contribution</b>
/// (spec FR-IDENT-010). The rollup view is tenant-stamped so the scope filter still applies, and
/// this surface sums across the rows in scope and returns one figure set carrying no organisation
/// identifier. A per-organisation breakdown is not a feature that was left out — it is a
/// disclosure, and it is asserted absent by <c>AggregateLeakageTests</c>.
/// </remarks>
public interface IDashboardReadModel
{
    /// <summary>Reads the platform rollup over the scope in effect.</summary>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One aggregate, or <see langword="null"/> when no window is in scope.</returns>
    Task<DashboardRollup?> GetPlatformAsync(CancellationToken cancellationToken);
}

/// <summary>The sortable fields for the organisation registry.</summary>
public static class TenantSortKeys
{
    /// <summary>
    /// The default sort for the registry.
    /// </summary>
    /// <remarks>
    /// <b>A stated divergence from the contract's default rule.</b> <c>contracts/README.md</c> says
    /// the default is <c>-createdAt</c>, but this resource's sortable set is <c>displayName</c> and
    /// <c>status</c> and contains no timestamp. Keyset paging needs a deterministic order, so the
    /// default is the registry's natural one — ascending by name — and the divergence is recorded
    /// rather than resolved silently (.claude/rules/70-adr.md).
    /// </remarks>
    public const string Default = "displayName";

    private static readonly FrozenDictionary<string, IKeysetSortKey<TenantRow>> _tenants =
        new IKeysetSortKey<TenantRow>[]
        {
            new KeysetSortKey<TenantRow, string>(
                "displayName",
                row => row.DisplayName,
                row => row.TenantId,
                KeysetValues.Render,
                KeysetValues.ParseText),
            new KeysetSortKey<TenantRow, TenantStatus>(
                "status",
                row => row.Status,
                row => row.TenantId,
                KeysetValues.RenderEnum,
                KeysetValues.ParseEnum<TenantStatus>),
        }.ToFrozenDictionary(key => key.Field, StringComparer.Ordinal);

    /// <summary>Sortable fields for the organisation registry.</summary>
    public static IReadOnlyDictionary<string, IKeysetSortKey<TenantRow>> Tenants => _tenants;
}

/// <summary>
/// Translates a contract-level page request into the persistence-level one.
/// </summary>
/// <remarks>Each module carries its own copy. See the note in <c>Synthia.Modules.Sessions</c>.</remarks>
internal static class KeysetTranslation
{
    public static KeysetDirection Direction(SortSpec sort) =>
        sort.Direction == SortDirection.Descending ? KeysetDirection.Descending : KeysetDirection.Ascending;

    public static KeysetAnchor? Anchor(KeysetPosition? position) =>
        position is null ? null : new KeysetAnchor(position.Value.SortValue, position.Value.Id);
}

/// <summary>Reads the organisation registry and the platform rollup.</summary>
internal sealed class TenantReadModel : ITenantReadModel, IDashboardReadModel
{
    private readonly SynthiaReadContext _context;

    public TenantReadModel(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<KeysetPage<TenantView>> ListAsync(
        TenantRegistryFilter filter,
        KeysetRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(filter);
        ArgumentNullException.ThrowIfNull(request);

        IQueryable<TenantRow> query = _context.Tenants;

        if (filter.Status is not null)
        {
            query = query.Where(row => row.Status == filter.Status);
        }

        KeysetSlice<TenantRow> slice = await KeysetQuery
            .TakeAsync(
                query,
                TenantSortKeys.Tenants[request.Sort.Field],
                KeysetTranslation.Direction(request.Sort),
                KeysetTranslation.Anchor(request.Position),
                request.Limit,
                cancellationToken)
            .ConfigureAwait(false);

        return KeysetPage.From(
            slice.Rows.Select(Project).ToList(),
            slice.Next?.SortValue,
            slice.Next?.Id);
    }

    public async Task<DashboardRollup?> GetPlatformAsync(CancellationToken cancellationToken)
    {
        // Aggregated in the database and returned as one row with no organisation identifier. The
        // per-organisation rows never leave this method, which is what keeps a count from becoming
        // a disclosure (spec FR-IDENT-010).
        List<DashboardRollupRow> rows = await _context.DashboardRollups
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        if (rows.Count == 0)
        {
            return null;
        }

        long sessions = rows.Sum(row => row.SessionCount);
        long approvals = rows.Sum(row => row.ApprovalCount);
        long unexecuted = rows.Sum(row => row.UnexecutedApprovalCount);

        // Weighted by session volume rather than averaged across organisations: an unweighted mean
        // lets a single small organisation move the platform figure, which is both wrong and a way
        // to infer that organisation's behaviour.
        double feedbackRate = sessions == 0
            ? 0
            : rows.Sum(row => row.FeedbackRate * row.SessionCount) / sessions;

        return new DashboardRollup(
            rows.Min(row => row.WindowStart),
            rows.Max(row => row.WindowEnd),
            sessions,
            approvals,
            unexecuted,
            feedbackRate);
    }

    private static TenantView Project(TenantRow row) =>
        new(
            row.TenantId,
            row.EntraTid,
            row.DisplayName,
            row.Status,
            row.CreatedAt,
            row.UpdatedAt,
            row.Version);
}
