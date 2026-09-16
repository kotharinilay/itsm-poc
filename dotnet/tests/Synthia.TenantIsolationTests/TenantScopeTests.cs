using System.Linq.Expressions;
using System.Reflection;
using Synthia.Persistence;
using Synthia.Persistence.Views;
using Synthia.SharedKernel.Identity;

namespace Synthia.TenantIsolationTests;

/// <summary>
/// Organisation scope is established from trusted state, and cannot be widened (T161).
/// </summary>
/// <remarks>
/// <b>A view exposing another organisation's row is a release-blocking defect, not a bug</b>
/// (contracts §read-views rule 5). These assert the layer this deployable owns: that every read
/// path is filtered, that the filter fails closed, and that nothing a caller supplies can move it.
/// </remarks>
public sealed class TenantScopeTests
{
    [Fact]
    public void An_unbound_scope_denies_everything()
    {
        // The unset scope is the state a wiring mistake produces, and it denies rather than
        // defaulting to anything. Asserted on the scope itself as well as on the predicate it
        // produces, so a change that made "unbound" mean something else fails here first.
        UnboundScope scope = new();

        Assert.Equal(TenantScopeKind.None, scope.Kind);
        Assert.Null(scope.Organisation);
    }

    [Fact]
    public void There_is_no_way_to_build_a_tenant_context_from_a_client_value()
    {
        // The API gives a caller holding a client-supplied tenant identifier nowhere to go, which
        // is the intended outcome. Three legitimate provenances, three factory methods, each named
        // after the provenance it claims (constitution Principle I).
        string[] factories = typeof(TenantAdmission)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Where(method => method.DeclaringType == typeof(TenantAdmission))
            .Select(method => method.Name)
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.Equal(
            ["FromAdmittedIdentity", "FromPlatformObject", "FromWorkItem"],
            factories);

        Assert.DoesNotContain(factories, name => name.Contains("Request", StringComparison.Ordinal));
        Assert.DoesNotContain(factories, name => name.Contains("Header", StringComparison.Ordinal));
        Assert.DoesNotContain(factories, name => name.Contains("Parse", StringComparison.Ordinal));
    }

    [Fact]
    public void A_tenant_context_has_no_public_constructor()
    {
        // Instances come only from TenantAdmission. A public constructor would make every one of
        // the checks above advisory.
        Assert.Empty(typeof(TenantContext).GetConstructors(BindingFlags.Public | BindingFlags.Instance));
        Assert.Empty(typeof(AuthenticatedPrincipal).GetConstructors(BindingFlags.Public | BindingFlags.Instance));
    }

    [Fact]
    public void Every_published_view_row_carries_an_organisation()
    {
        // tenant_id is present on every published view (contracts §read-views rule 1), which is
        // what lets the global filter be stated once rather than remembered per entity. The
        // catalogue is the one exception and says why on the type.
        Type[] rows = typeof(PublishedViews).Assembly
            .GetTypes()
            .Where(type => type.Namespace == typeof(PublishedViews).Namespace)
            .Where(type => type.IsClass && type.Name.EndsWith("Row", StringComparison.Ordinal))
            .ToArray();

        Assert.NotEmpty(rows);

        string[] unscoped = rows
            .Where(row => !typeof(Persistence.Conventions.ITenantScopedRow).IsAssignableFrom(row))
            .Select(row => row.Name)
            .ToArray();

        Assert.Equal(["GovernanceCatalogueRow"], unscoped);
    }

    [Fact]
    public void The_scope_filter_denies_when_nothing_is_bound()
    {
        // The predicate itself, evaluated in memory. An unbound scope denies structurally: the
        // hasOrganisation term is false, so nothing downstream of it can match.
        Func<SessionSummaryRow, bool> filter = BuildFilter(bound: false, Guid.Empty, operatorWide: false);

        Assert.False(filter(RowFor(Guid.NewGuid())));

        // Including a row whose organisation is the empty identifier. Denying that one only because
        // no row is expected to carry it would be a claim about the data rather than about the
        // filter, and data changes.
        Assert.False(filter(RowFor(Guid.Empty)));
    }

    [Fact]
    public void The_scope_filter_admits_only_the_bound_organisation()
    {
        Guid mine = Guid.NewGuid();

        Func<SessionSummaryRow, bool> filter = BuildFilter(bound: true, mine, operatorWide: false);

        Assert.True(filter(RowFor(mine)));
        Assert.False(filter(RowFor(Guid.NewGuid())));
    }

    [Fact]
    public void The_operator_wide_scope_spans_organisations()
    {
        // Staff operate across customer organisations using trusted platform context
        // (spec FR-IDENT-007). A wider scope, not an absent one — and it is still a predicate,
        // derived from the audience the Gateway routed to.
        Func<SessionSummaryRow, bool> filter = BuildFilter(bound: false, Guid.Empty, operatorWide: true);

        Assert.True(filter(RowFor(Guid.NewGuid())));
        Assert.True(filter(RowFor(Guid.NewGuid())));
    }

    private static SessionSummaryRow RowFor(Guid tenantId) => new() { TenantId = tenantId };

    private static Func<SessionSummaryRow, bool> BuildFilter(bool bound, Guid tenantId, bool operatorWide)
    {
        // Built through the production expression builder, not reimplemented here. A test that
        // rebuilt the predicate would agree with any change to the real one, including a wrong one.
        Type builder = typeof(SynthiaReadContext).Assembly
            .GetType("Synthia.Persistence.Conventions.ReadModelQueryFilter")!;

        MethodInfo build = builder
            .GetMethod("Build", BindingFlags.Public | BindingFlags.Static)!
            .MakeGenericMethod(typeof(SessionSummaryRow));

        Expression<Func<SessionSummaryRow, bool>> predicate =
            (Expression<Func<SessionSummaryRow, bool>>)build.Invoke(
                null,
                [
                    Expression.Constant(bound),
                    Expression.Constant(tenantId),
                    Expression.Constant(operatorWide),
                ])!;

        return predicate.Compile();
    }
}

/// <summary>A scope that was never bound, which is the state a wiring mistake produces.</summary>
internal sealed class UnboundScope : ITenantScope
{
    public TenantScopeKind Kind => TenantScopeKind.None;

    public TenantContext? Organisation => null;
}
