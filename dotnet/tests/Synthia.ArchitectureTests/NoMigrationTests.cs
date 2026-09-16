using System.Reflection;
using Microsoft.EntityFrameworkCore;
using Synthia.Persistence;

namespace Synthia.ArchitectureTests;

/// <summary>
/// This deployable owns no schema (T068).
/// </summary>
/// <remarks>
/// <para>
/// <b><c>Database.Migrate()</c>, <c>EnsureCreated()</c> and EF migration files are prohibited
/// here</b> (ADR-0003, contracts §read-views). RagCore owns every table, every view and every
/// migration; this side holds <c>SELECT</c> on published views and nothing else.
/// </para>
/// <para>
/// The constitution records the general rule — EF migrations run in CI and deployment, never at
/// startup — and records that <b>it has no current application in this platform</b>. If .NET is
/// ever intended to own schema, ADR-0001 and ADR-0003 must be amended before these tests are
/// changed, not afterwards.
/// </para>
/// </remarks>
public sealed class NoMigrationTests
{
    [Fact]
    public void No_source_file_calls_Migrate_or_EnsureCreated()
    {
        // Counted over source rather than IL: a call that is present is what matters, and the
        // method names are distinctive enough that a false positive would have to be somebody
        // writing about them — which is what the comment-bearing files below would be.
        string[] prohibited = ["Database.Migrate(", "EnsureCreated(", "MigrateAsync(", "EnsureCreatedAsync("];

        List<string> offending = [];

        foreach (string api in prohibited)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(api))
            {
                offending.Add($"{file} -> {api}");
            }
        }

        Assert.True(
            offending.Count == 0,
            "A production file reaches for schema management. Alembic owns every migration " +
            "(ADR-0003):\n  " + string.Join("\n  ", offending));
    }

    [Fact]
    public void No_migrations_folder_exists()
    {
        DirectoryInfo source = new(Path.Combine(ProjectGraph.SolutionDirectory().FullName, "src"));

        List<string> folders = source
            .GetDirectories("Migrations", SearchOption.AllDirectories)
            .Select(directory => directory.FullName)
            .ToList();

        Assert.True(
            folders.Count == 0,
            "A Migrations folder exists in the read-only deployable:\n  " + string.Join("\n  ", folders));
    }

    [Fact]
    public void No_type_derives_from_the_ef_migration_base_types()
    {
        // The compiled form of the same rule. A migration generated into an unusual folder would
        // pass the folder check and fail here.
        string[] migrationTypes =
        [
            "Microsoft.EntityFrameworkCore.Migrations.Migration",
            "Microsoft.EntityFrameworkCore.Infrastructure.ModelSnapshot",
        ];

        List<string> offending = [];

        foreach (Type type in typeof(SynthiaReadContext).Assembly.GetTypes())
        {
            for (Type? candidate = type.BaseType; candidate is not null; candidate = candidate.BaseType)
            {
                if (Array.Exists(migrationTypes, name => string.Equals(candidate.FullName, name, StringComparison.Ordinal)))
                {
                    offending.Add(type.FullName ?? type.Name);
                }
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }

    [Fact]
    public void Every_mapped_entity_is_a_view_rather_than_a_table()
    {
        // The mapping-level guarantee: EF has no table to write to, so even a mistakenly tracked
        // entity has nowhere to go. This is the second of the three independent enforcements the
        // read context documents.
        using SynthiaReadContext context = ReadContextFactory.Create();

        List<string> tables = context.Model.GetEntityTypes()
            .Where(entity => entity.GetViewName() is null)
            .Select(entity => $"{entity.ClrType.Name} -> {entity.GetTableName() ?? "(unmapped)"}")
            .ToList();

        Assert.True(
            tables.Count == 0,
            "An entity is mapped to a table rather than a published view:\n  " +
            string.Join("\n  ", tables));
    }

    [Fact]
    public void Every_mapped_entity_reads_a_published_view_by_its_contract_name()
    {
        // Names are the contract (contracts §read-views). A view mapped under a name that is not on
        // the published list is a coupling to something RagCore never promised to keep.
        using SynthiaReadContext context = ReadContextFactory.Create();

        List<string> unpublished = context.Model.GetEntityTypes()
            .Select(entity => entity.GetViewName())
            .Where(view => view is not null)
            .Where(view => !Persistence.Views.PublishedViews.All.Contains(view!, StringComparer.Ordinal))
            .Select(view => view!)
            .ToList();

        Assert.True(
            unpublished.Count == 0,
            "An entity reads a view outside the published contract:\n  " +
            string.Join("\n  ", unpublished));
    }

    [Fact]
    public void Saving_changes_is_refused()
    {
        // The third enforcement, and the one that survives somebody mapping a table by mistake.
        using SynthiaReadContext context = ReadContextFactory.Create();

        InvalidOperationException refusal = Assert.Throws<InvalidOperationException>(() => context.SaveChanges());

        Assert.Contains("read-only", refusal.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Saving_changes_asynchronously_is_refused()
    {
        // Asserted separately because the async overload is a different method, and overriding one
        // of the pair is a real and easy mistake.
        using SynthiaReadContext context = ReadContextFactory.Create();

        await Assert.ThrowsAsync<InvalidOperationException>(() => context.SaveChangesAsync(CancellationToken.None));
    }

    [Fact]
    public void The_read_context_tracks_nothing_by_default()
    {
        // AsNoTracking is the default rather than a per-query decision (constitution §.NET data
        // access). Nothing is ever written back, so a change tracker would be pure cost — and a
        // tracked read model is an invitation to try.
        using SynthiaReadContext context = ReadContextFactory.Create();

        Assert.Equal(QueryTrackingBehavior.NoTracking, context.ChangeTracker.QueryTrackingBehavior);
    }

    [Fact]
    public void No_production_type_holds_a_DbSet_outside_the_read_context()
    {
        // A second context would be a second set of query filters to keep honest, and the first one
        // somebody forgot would be the one that leaked.
        List<string> offending = [];

        foreach (Type type in typeof(SynthiaReadContext).Assembly.GetTypes())
        {
            if (type == typeof(SynthiaReadContext))
            {
                continue;
            }

            if (type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
                .Any(property => property.PropertyType.IsGenericType &&
                                 property.PropertyType.GetGenericTypeDefinition() == typeof(DbSet<>)))
            {
                offending.Add(type.Name);
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }
}
