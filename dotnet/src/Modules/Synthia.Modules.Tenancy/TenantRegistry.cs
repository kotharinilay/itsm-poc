using Microsoft.EntityFrameworkCore;
using Synthia.Persistence;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Identity;

namespace Synthia.Modules.Tenancy;

/// <summary>
/// What the registry knows about one organisation, as admission needs it.
/// </summary>
/// <param name="TenantId">The platform identifier.</param>
/// <param name="EntraTenantId">The validated <c>tid</c> it maps to.</param>
/// <param name="Status">The organisation's admission state.</param>
public readonly record struct TenantAdmissionRecord(
    TenantId TenantId,
    EntraTenantId EntraTenantId,
    TenantStatus Status);

/// <summary>
/// Resolves a validated Entra tenant into the platform organisation it maps to.
/// </summary>
/// <remarks>
/// <b>This is tenant admission: trusted identity plus platform tenant-registry state, and nothing
/// else</b> (constitution Principle I). It runs before a scope exists, which makes it the one
/// bootstrap in the read path — see the implementation for why that is safe and how it is fenced.
/// </remarks>
public interface ITenantRegistry
{
    /// <summary>
    /// Finds the organisation a validated <c>tid</c> maps to.
    /// </summary>
    /// <param name="entraTenantId">The <c>tid</c> the Gateway derived. Never a client field.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>The registry record, or <see langword="null"/> when the tenant is not registered.</returns>
    Task<TenantAdmissionRecord?> FindAsync(EntraTenantId entraTenantId, CancellationToken cancellationToken);
}

/// <summary>Reads the organisation registry for admission.</summary>
internal sealed class TenantRegistry : ITenantRegistry
{
    private readonly SynthiaReadContext _context;

    public TenantRegistry(SynthiaReadContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        _context = context;
    }

    public async Task<TenantAdmissionRecord?> FindAsync(
        EntraTenantId entraTenantId,
        CancellationToken cancellationToken)
    {
        Guid tid = entraTenantId.Value;

        // THE ONE PLACE THE GLOBAL TENANT FILTER IS BYPASSED, AND THE ONLY PLACE IT MAY BE.
        //
        // Admission is a bootstrap: the filter is built from the organisation in scope, and this
        // query is what establishes that organisation. Filtering it by its own answer would mean
        // no request could ever be admitted.
        //
        // It is safe because the predicate IS the admission rule. entra_tid is the only value that
        // may be matched against a token-derived tenant (data-model.md §Tenant mapping), the value
        // matched here came from the Gateway-derived header contract, and exactly one row can
        // match because entra_tid is unique. So this reads one organisation's registry row using
        // that organisation's own validated identifier — it cannot be steered to another.
        //
        // NoIgnoredQueryFilterTests asserts this is the only IgnoreQueryFilters call in the tree.
        // If a second one appears, one of them is a tenant-isolation defect.
        TenantRow? row = await _context.Tenants
            .IgnoreQueryFilters()
            .Where(candidate => candidate.EntraTid == tid)
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

        if (row is null)
        {
            return null;
        }

        return new TenantAdmissionRecord(
            new TenantId(row.TenantId),
            new EntraTenantId(row.EntraTid),
            row.Status);
    }
}
