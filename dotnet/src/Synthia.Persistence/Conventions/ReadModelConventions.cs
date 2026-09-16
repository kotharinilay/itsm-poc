namespace Synthia.Persistence.Conventions;

/// <summary>
/// Every row this deployable can see carries the organisation that owns it.
/// </summary>
/// <remarks>
/// <b><c>tenant_id</c> is present on every published view</b> (contracts §read-views rule 1). The
/// interface exists so the global query filter can be stated once, generically, rather than
/// remembered per entity — a filter you have to remember is a filter that will eventually be
/// forgotten.
/// </remarks>
public interface ITenantScopedRow
{
    /// <summary>The organisation that owns this row.</summary>
    Guid TenantId { get; }
}

/// <summary>
/// The standard audit columns (constitution §.NET data access, data-model.md §Conventions).
/// </summary>
/// <remarks>
/// <c>created_by</c> and <c>updated_by</c> apply where a principal is meaningful and are therefore
/// not on this interface — an agent-authored row has no principal, and a nullable column that is
/// always null on half the tables is worse than a column that is not claimed to exist.
/// </remarks>
public interface IAuditedRow
{
    /// <summary>When the row was created.</summary>
    DateTimeOffset CreatedAt { get; }

    /// <summary>When the row was last changed.</summary>
    DateTimeOffset UpdatedAt { get; }
}

/// <summary>
/// The optimistic-concurrency token carried by every mutable row.
/// </summary>
/// <remarks>
/// <para>
/// <b>Optimistic concurrency only</b> — no pessimistic and no distributed locking exists anywhere
/// in the platform (research R-018). A losing writer sees a version conflict and re-reads rather
/// than blocking.
/// </para>
/// <para>
/// The monolith never writes, so it never loses a race. It surfaces the version anyway, because a
/// client that read a row here and then acts on it through RagCore needs the value it read — and
/// a read model that drops the token quietly converts optimistic concurrency into last-write-wins
/// one layer up.
/// </para>
/// <para>
/// One exemption exists platform-wide and is named in data-model.md: <c>idempotency_record</c>,
/// whose primary key already serialises every concurrent writer. No further exemption exists.
/// </para>
/// </remarks>
public interface IVersionedRow
{
    /// <summary>The row version at the time it was read.</summary>
    int Version { get; }
}

/// <summary>
/// The soft-delete convention. <b>No scaffold entity implements it, and none is intended to.</b>
/// </summary>
/// <remarks>
/// <para>
/// The convention is: a row requiring recoverable deletion carries <c>deleted_at</c>, and it is
/// excluded by a global query filter and by every published view. <see cref="SynthiaReadContext"/>
/// applies that filter automatically to any entity implementing this interface, so adopting the
/// convention later is a declaration rather than a change to query code.
/// </para>
/// <para>
/// <b>Nothing uses it today, deliberately</b> (data-model.md §Soft delete). Erasure is a hard
/// delete, because a soft-deleted row is still the organisation's data and a flag would defeat the
/// requirement. Retention is likewise a removal, not a flag. <c>NoSoftDeleteTests</c> asserts the
/// interface stays unimplemented, so the first table to adopt it has to say why in data-model.md
/// first.
/// </para>
/// </remarks>
public interface ISoftDeletableRow
{
    /// <summary>When the row was soft-deleted, or <see langword="null"/> while live.</summary>
    DateTimeOffset? DeletedAt { get; }
}
