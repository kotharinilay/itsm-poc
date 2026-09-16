using System.Linq.Expressions;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Synthia.Persistence.Conventions;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Governance;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;
using Synthia.SharedKernel.Work;

namespace Synthia.Persistence;

/// <summary>
/// The read context over the published views. <b>Reads only, and cannot be made to write.</b>
/// </summary>
/// <remarks>
/// <para>
/// RagCore owns every table and every migration; this deployable holds <c>SELECT</c> on published
/// views only — no table access, no DDL, no migrations (contracts §read-views). That is enforced in
/// three independent places, because one of them is always the one that gets removed:
/// </para>
/// <list type="number">
///   <item>By grant, in the database. The runtime principal cannot write.</item>
///   <item>By mapping: every entity is <c>ToView</c>, so EF has no table to write to.</item>
///   <item>By this type, which throws on any attempt to save.</item>
/// </list>
/// <para>
/// <c>Database.Migrate()</c>, <c>EnsureCreated()</c> and EF migration files are prohibited here and
/// <c>NoMigrationTests</c> enforces their absence (ADR-0003).
/// </para>
/// </remarks>
public sealed class SynthiaReadContext : DbContext
{
    private readonly ITenantScope _tenantScope;

    /// <summary>Creates the context.</summary>
    /// <param name="options">Options supplied by the composition root.</param>
    /// <param name="tenantScope">The organisation in scope for this unit of work.</param>
    public SynthiaReadContext(DbContextOptions<SynthiaReadContext> options, ITenantScope tenantScope)
        : base(options)
    {
        ArgumentNullException.ThrowIfNull(tenantScope);

        _tenantScope = tenantScope;
    }

    /// <summary>Session listings.</summary>
    public DbSet<SessionSummaryRow> SessionSummaries => Set<SessionSummaryRow>();

    /// <summary>Conversation history, already excluding rows past their retention window.</summary>
    public DbSet<SessionMessageRow> SessionMessages => Set<SessionMessageRow>();

    /// <summary>Step trail.</summary>
    public DbSet<SessionStepRow> SessionSteps => Set<SessionStepRow>();

    /// <summary>Current feedback signals.</summary>
    public DbSet<MessageFeedbackRow> MessageFeedback => Set<MessageFeedbackRow>();

    /// <summary>Work state.</summary>
    public DbSet<WorkItemRow> WorkItems => Set<WorkItemRow>();

    /// <summary>Pending approvals.</summary>
    public DbSet<ApprovalQueueRow> ApprovalQueue => Set<ApprovalQueueRow>();

    /// <summary>Approved but never executed.</summary>
    public DbSet<ApprovalUnexecutedRow> UnexecutedApprovals => Set<ApprovalUnexecutedRow>();

    /// <summary>Audit search.</summary>
    public DbSet<AuditEventRow> AuditEvents => Set<AuditEventRow>();

    /// <summary>Catalogue browsing.</summary>
    public DbSet<GovernanceCatalogueRow> GovernanceCatalogue => Set<GovernanceCatalogueRow>();

    /// <summary>Organisation registry.</summary>
    public DbSet<TenantRow> Tenants => Set<TenantRow>();

    /// <summary>Pre-aggregated platform counts.</summary>
    public DbSet<DashboardRollupRow> DashboardRollups => Set<DashboardRollupRow>();

    /// <summary>
    /// Whether an organisation has been bound at all.
    /// </summary>
    /// <remarks>
    /// <b>This is what makes an unbound scope deny structurally rather than by luck.</b> The filter
    /// ANDs this in front of the identifier comparison, so a request that reached a query without
    /// an established organisation reads nothing whatever the rows happen to contain. Failing
    /// closed here is what keeps "there is no unfiltered path" true through a wiring mistake.
    /// </remarks>
    public bool HasOrganisationScope => _tenantScope.Organisation is not null;

    /// <summary>The organisation every query is filtered to, when one is bound.</summary>
    public Guid CurrentTenantId => _tenantScope.Organisation?.TenantId.Value ?? Guid.Empty;

    /// <summary>
    /// Whether this unit of work reads across customer organisations.
    /// </summary>
    /// <remarks>
    /// True only for a staff caller on the staff audience. The <c>tenantId</c> query filter that
    /// staff resources accept narrows <i>within</i> this scope; nothing a caller supplies can set
    /// it (contracts §README rule 1).
    /// </remarks>
    public bool IsOperatorWide => _tenantScope.Kind == TenantScopeKind.OperatorWide;

    /// <summary>Not supported. This deployable writes nothing.</summary>
    /// <param name="acceptAllChangesOnSuccess">Ignored.</param>
    /// <returns>Never returns.</returns>
    /// <exception cref="InvalidOperationException">Always.</exception>
    public override int SaveChanges(bool acceptAllChangesOnSuccess) => throw ReadOnly();

    /// <summary>Not supported. This deployable writes nothing.</summary>
    /// <param name="acceptAllChangesOnSuccess">Ignored.</param>
    /// <param name="cancellationToken">Ignored.</param>
    /// <returns>Never returns.</returns>
    /// <exception cref="InvalidOperationException">Always.</exception>
    public override Task<int> SaveChangesAsync(
        bool acceptAllChangesOnSuccess,
        CancellationToken cancellationToken = default) => throw ReadOnly();

    /// <inheritdoc/>
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        ArgumentNullException.ThrowIfNull(modelBuilder);

        base.OnModelCreating(modelBuilder);

        MapSessionViews(modelBuilder);
        MapWorkAndApprovalViews(modelBuilder);
        MapGovernanceViews(modelBuilder);
        MapTenancyViews(modelBuilder);

        ApplyColumnNaming(modelBuilder);
    }

    private static InvalidOperationException ReadOnly() =>
        new("The .NET monolith is read-only (ADR-0001). Every state change belongs to RagCore, " +
            "which reaches this database through its own migrations and writes. If a write is " +
            "genuinely needed here, ADR-0001 and ADR-0003 must be amended first.");

    private static void ApplyColumnNaming(ModelBuilder modelBuilder)
    {
        foreach (Microsoft.EntityFrameworkCore.Metadata.IMutableEntityType entity in
            modelBuilder.Model.GetEntityTypes())
        {
            foreach (Microsoft.EntityFrameworkCore.Metadata.IMutableProperty property in
                entity.GetProperties())
            {
                property.SetColumnName(SnakeCaseNaming.ToSnakeCase(property.Name));
            }
        }
    }

    private static void MapLowerSnakeEnum<TRow, TEnum>(
        EntityTypeBuilder<TRow> entity,
        Expression<Func<TRow, TEnum>> property)
        where TRow : class
        where TEnum : struct, Enum =>
        entity.Property(property).HasConversion(new LowerSnakeCaseEnumConverter<TEnum>());

    private static void MapNullableLowerSnakeEnum<TRow, TEnum>(
        EntityTypeBuilder<TRow> entity,
        Expression<Func<TRow, TEnum?>> property)
        where TRow : class
        where TEnum : struct, Enum =>
        entity.Property(property).HasConversion(new LowerSnakeCaseEnumConverter<TEnum>());

    private void MapSessionViews(ModelBuilder modelBuilder)
    {
        EntityTypeBuilder<SessionSummaryRow> sessions =
            TenantScopedView<SessionSummaryRow>(modelBuilder, PublishedViews.SessionSummary);
        sessions.HasKey(row => row.SessionId);
        MapLowerSnakeEnum(sessions, row => row.State);

        EntityTypeBuilder<SessionMessageRow> messages =
            TenantScopedView<SessionMessageRow>(modelBuilder, PublishedViews.SessionMessage);
        messages.HasKey(row => row.MessageId);
        MapLowerSnakeEnum(messages, row => row.SenderKind);

        EntityTypeBuilder<SessionStepRow> steps =
            TenantScopedView<SessionStepRow>(modelBuilder, PublishedViews.SessionStep);
        steps.HasKey(row => row.StepId);

        EntityTypeBuilder<MessageFeedbackRow> feedback =
            TenantScopedView<MessageFeedbackRow>(modelBuilder, PublishedViews.MessageFeedback);
        feedback.HasKey(row => row.MessageId);
        MapLowerSnakeEnum(feedback, row => row.Signal);
    }

    private void MapWorkAndApprovalViews(ModelBuilder modelBuilder)
    {
        EntityTypeBuilder<WorkItemRow> work =
            TenantScopedView<WorkItemRow>(modelBuilder, PublishedViews.WorkItem);
        work.HasKey(row => row.WorkItemId);
        work.Property(row => row.Version).IsConcurrencyToken();
        MapLowerSnakeEnum(work, row => row.State);
        MapLowerSnakeEnum(work, row => row.ApprovalState);

        EntityTypeBuilder<ApprovalQueueRow> queue =
            TenantScopedView<ApprovalQueueRow>(modelBuilder, PublishedViews.ApprovalQueue);
        queue.HasKey(row => row.ApprovalId);
        queue.Property(row => row.Version).IsConcurrencyToken();

        EntityTypeBuilder<ApprovalUnexecutedRow> unexecuted =
            TenantScopedView<ApprovalUnexecutedRow>(modelBuilder, PublishedViews.ApprovalUnexecuted);
        unexecuted.HasKey(row => row.ApprovalId);
        unexecuted.Property(row => row.Version).IsConcurrencyToken();
    }

    private void MapGovernanceViews(ModelBuilder modelBuilder)
    {
        // The catalogue is platform-wide, so it carries no tenant filter. Entitlement is what is
        // tenant-scoped, and no published view exposes it: tenant_entitlement holds credential
        // references, and a view carrying one would breach read-views rule 2.
        EntityTypeBuilder<GovernanceCatalogueRow> catalogue = modelBuilder.Entity<GovernanceCatalogueRow>();
        catalogue.ToView(PublishedViews.GovernanceCatalogue, PublishedViews.Schema);
        catalogue.HasKey(row => new { row.CatalogueId, row.Version });
        MapLowerSnakeEnum(catalogue, row => row.Kind);
        catalogue.Property(row => row.DefaultTreatment)
            .HasConversion(new UpperSnakeCaseEnumConverter<ExecutionTreatment>());
        catalogue.Property(row => row.AcceptedRoles)
            .HasConversion(
                roles => roles.ToArray(),
                stored => stored.ToList(),
                new ValueComparer<IReadOnlyList<string>>(
                    (left, right) => left != null && right != null && left.SequenceEqual(right),
                    roles => roles.Aggregate(0, (hash, role) => HashCode.Combine(hash, role.GetHashCode(StringComparison.Ordinal))),
                    roles => roles.ToList()));

        EntityTypeBuilder<AuditEventRow> audit =
            TenantScopedView<AuditEventRow>(modelBuilder, PublishedViews.AuditEvent);
        audit.HasKey(row => row.AuditId);
        MapLowerSnakeEnum(audit, row => row.ExecutionMethod);
        MapNullableLowerSnakeEnum(audit, row => row.Verification);
    }

    private void MapTenancyViews(ModelBuilder modelBuilder)
    {
        EntityTypeBuilder<TenantRow> tenants =
            TenantScopedView<TenantRow>(modelBuilder, PublishedViews.Tenant);
        tenants.HasKey(row => row.TenantId);
        tenants.Property(row => row.Version).IsConcurrencyToken();
        MapLowerSnakeEnum(tenants, row => row.Status);

        EntityTypeBuilder<DashboardRollupRow> rollups =
            TenantScopedView<DashboardRollupRow>(modelBuilder, PublishedViews.DashboardRollup);
        rollups.HasKey(row => new { row.TenantId, row.WindowStart });
    }

    private EntityTypeBuilder<TRow> TenantScopedView<TRow>(ModelBuilder modelBuilder, string view)
        where TRow : class, ITenantScopedRow
    {
        EntityTypeBuilder<TRow> entity = modelBuilder.Entity<TRow>();

        entity.ToView(view, PublishedViews.Schema);
        entity.HasQueryFilter(
            ReadModelQueryFilter.Build<TRow>(
                Expression.Property(Expression.Constant(this), nameof(HasOrganisationScope)),
                Expression.Property(Expression.Constant(this), nameof(CurrentTenantId)),
                Expression.Property(Expression.Constant(this), nameof(IsOperatorWide))));

        return entity;
    }
}
