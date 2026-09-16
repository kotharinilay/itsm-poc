using System.Linq.Expressions;

namespace Synthia.Persistence.Conventions;

/// <summary>
/// Builds the global query filter every published view is read through.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the "no unfiltered path" rule made structural.</b> Tenant isolation MUST apply at
/// every layer and MUST NOT rest on a single chokepoint (constitution Principle IV) — but within
/// this layer, the filter being unavoidable is the point. A repository method cannot omit the
/// organisation because there is no method that takes it, and no query that does not have it.
/// </para>
/// <para>
/// The filter is composed rather than written per entity so the soft-delete term appears the
/// moment an entity adopts <see cref="ISoftDeletableRow"/>, without anyone having to remember to
/// add it. No entity adopts it today (data-model.md §Soft delete).
/// </para>
/// </remarks>
internal static class ReadModelQueryFilter
{
    /// <summary>
    /// Builds <c>row =&gt; (hasOrganisation &amp;&amp; row.TenantId == current) || operatorWide</c>,
    /// plus <c>&amp;&amp; row.DeletedAt == null</c> when the row is soft-deletable.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>The operator-wide term is a scope, not an escape hatch.</b> It is true only for a staff
    /// caller on the staff audience, derived from the route the Gateway matched and the credential
    /// class it carried (spec FR-IDENT-007).
    /// </para>
    /// <para>
    /// <b>The <c>hasOrganisation</c> term is what makes the unset scope deny structurally.</b>
    /// Without it the predicate reduces to <c>TenantId == Guid.Empty</c>, which denies only because
    /// no row is expected to carry that value — a claim about the data, not about the filter. With
    /// it, an unbound scope matches nothing whatever the rows contain.
    /// </para>
    /// </remarks>
    /// <typeparam name="TRow">The view row type.</typeparam>
    /// <param name="hasOrganisation">
    /// An expression yielding whether an organisation has been bound at all.
    /// </param>
    /// <param name="currentTenantId">
    /// An expression yielding the organisation in scope. Evaluated per query, so one context
    /// instance serves one request and the model is still cached.
    /// </param>
    /// <param name="operatorWide">An expression yielding whether the scope spans organisations.</param>
    /// <returns>The predicate to hand to <c>HasQueryFilter</c>.</returns>
    public static Expression<Func<TRow, bool>> Build<TRow>(
        Expression hasOrganisation,
        Expression currentTenantId,
        Expression operatorWide)
        where TRow : class, ITenantScopedRow
    {
        ArgumentNullException.ThrowIfNull(hasOrganisation);
        ArgumentNullException.ThrowIfNull(currentTenantId);
        ArgumentNullException.ThrowIfNull(operatorWide);

        ParameterExpression row = Expression.Parameter(typeof(TRow), "row");

        Expression predicate = Expression.OrElse(
            Expression.AndAlso(
                hasOrganisation,
                Expression.Equal(
                    Expression.Property(row, nameof(ITenantScopedRow.TenantId)),
                    currentTenantId)),
            operatorWide);

        if (typeof(ISoftDeletableRow).IsAssignableFrom(typeof(TRow)))
        {
            predicate = Expression.AndAlso(
                predicate,
                Expression.Equal(
                    Expression.Property(row, nameof(ISoftDeletableRow.DeletedAt)),
                    Expression.Constant(null, typeof(DateTimeOffset?))));
        }

        return Expression.Lambda<Func<TRow, bool>>(predicate, row);
    }
}
