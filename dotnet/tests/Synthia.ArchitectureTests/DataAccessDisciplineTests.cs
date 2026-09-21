using System.Reflection;
using Synthia.Persistence.Conventions;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The data-access positions the frozen documents take, asserted so they cannot drift silently.
/// </summary>
/// <remarks>
/// Each of these is a rule that data-model.md states <b>and then states has no current
/// application</b>. A rule with no current application is the easiest kind to break, because
/// breaking it looks like adding a feature rather than removing a constraint.
/// </remarks>
public sealed class DataAccessDisciplineTests
{
    [Fact]
    public void The_global_query_filter_is_bypassed_in_exactly_one_place()
    {
        // Tenant admission is a bootstrap: the filter is built from the organisation in scope, and
        // the registry lookup is what establishes that organisation. It is safe because the
        // predicate IS the admission rule — entra_tid is the only value that may be matched against
        // a token-derived tenant, and it is unique.
        //
        // A SECOND occurrence would not be a bootstrap. It would be a tenant-isolation defect
        // (A1 §4.5, A2 P03).
        IReadOnlyList<string> files = SourceTree.ProductionFilesContaining("IgnoreQueryFilters");

        Assert.True(
            files.Count == 1 && files[0] == "TenantRegistry.cs",
            "The tenant filter is bypassed somewhere other than tenant admission:\n  " +
            string.Join("\n  ", files));
    }

    [Fact]
    public void No_entity_uses_soft_delete()
    {
        // No entity in the scaffold uses it, and none is intended to (data-model.md §Soft delete).
        // Erasure is a hard delete, because a soft-deleted row is still the organisation's data and
        // a flag would defeat the requirement. Retention is likewise a removal, not a flag.
        //
        // The convention is implemented and the filter composes automatically, so adopting it later
        // is a declaration. The first table to adopt it states why in data-model.md first — and
        // this test failing is how that conversation starts.
        List<string> adopters = [];

        foreach (Assembly assembly in ProductionAssemblies.All)
        {
            adopters.AddRange(assembly.GetTypes()
                .Where(type => typeof(ISoftDeletableRow).IsAssignableFrom(type) && type.IsClass)
                .Select(type => type.Name));
        }

        Assert.True(
            adopters.Count == 0,
            "An entity has adopted soft delete. data-model.md §Soft delete says none does, and the " +
            "first one to must say why there before it does so here:\n  " + string.Join("\n  ", adopters));
    }

    [Fact]
    public void No_transaction_sets_an_isolation_level()
    {
        // Read Committed everywhere; no Serializable transaction exists (data-model.md §Isolation
        // level). Every invariant in the model is enforced by a constraint or an atomic conditional
        // update rather than by isolation level — the claim is on the work item, first-verdict-wins
        // on a unique index, duplicate effects on an idempotency key.
        //
        // If a future invariant genuinely needs Serializable, it is named in data-model.md first,
        // because an unnamed Serializable transaction is indistinguishable from a copy-paste.
        string[] tells = ["IsolationLevel.", "BeginTransaction(", "SERIALIZABLE"];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(
            offending.Count == 0,
            "A transaction boundary or isolation level appears in a read-only deployable:\n  " +
            string.Join("\n  ", offending));
    }

    [Fact]
    public void No_distributed_lock_exists()
    {
        // Distributed locking MUST NOT be an architectural primitive (.claude/rules/20-dotnet.md BL-30).
        // It adds lock loss, lease expiry and split brain to solve a problem the database solves
        // for free, and it would put the fifteen-minute window at the mercy of a lock service.
        string[] tells = ["DistributedLock", "AcquireLock", "LeaseId", "RedLock"];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }

    [Fact]
    public void Every_versioned_row_exposes_its_concurrency_token()
    {
        // Optimistic concurrency only (research R-018). The monolith never writes and so never
        // loses a race, but a read model that drops the token quietly converts optimistic
        // concurrency into last-write-wins one layer up — the caller reads here and acts through
        // RagCore, and needs the value it read.
        using Persistence.SynthiaReadContext context = ReadContextFactory.Create();

        List<string> missing = [];

        foreach (Microsoft.EntityFrameworkCore.Metadata.IEntityType entity in context.Model.GetEntityTypes())
        {
            if (!typeof(IVersionedRow).IsAssignableFrom(entity.ClrType))
            {
                continue;
            }

            Microsoft.EntityFrameworkCore.Metadata.IProperty? version =
                entity.FindProperty(nameof(IVersionedRow.Version));

            if (version is null || !version.IsConcurrencyToken)
            {
                missing.Add(entity.ClrType.Name);
            }
        }

        Assert.True(
            missing.Count == 0,
            "A versioned row does not map its version as a concurrency token:\n  " +
            string.Join("\n  ", missing));
    }

    [Fact]
    public void No_raw_sql_is_executed()
    {
        // Parameterized queries only (.claude/rules/20-dotnet.md §20.4). LINQ parameterizes by
        // construction; the raw-SQL escape hatches are where injection becomes possible again, and
        // this deployable has no query that needs one.
        string[] tells = ["FromSqlRaw", "ExecuteSqlRaw", "FromSqlInterpolated", "ExecuteSqlInterpolated"];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }
}
