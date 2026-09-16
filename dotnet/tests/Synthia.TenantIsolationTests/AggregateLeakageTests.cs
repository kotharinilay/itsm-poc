using System.Reflection;
using Synthia.Contracts.ReadModels;

namespace Synthia.TenantIsolationTests;

/// <summary>
/// No count, ranking or distribution reveals a single organisation's contribution (T162).
/// </summary>
/// <remarks>
/// <b>Aggregated and derived figures MUST NOT reveal another organisation's data through counts,
/// rankings, distributions or any other indirect route</b> (spec FR-IDENT-010). A figure spanning
/// organisations may be exposed only where no single organisation's contribution is identifiable.
/// <para>
/// The direct disclosure — a tenant identifier on the aggregate — is the one to test, because it is
/// the one a refactor reintroduces. Statistical disclosure through small cell sizes is a real and
/// separate concern; it is not solvable by a shape assertion and is not claimed to be solved here.
/// </para>
/// </remarks>
public sealed class AggregateLeakageTests
{
    [Fact]
    public void The_platform_rollup_carries_no_organisation_identifier()
    {
        // The per-organisation rows exist in the view and are summed inside the read model. If one
        // reached this contract, the dashboard would name which organisation contributed what.
        string[] identifying = typeof(DashboardRollup)
            .GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(property => property.Name)
            .Where(name =>
                name.Contains("Tenant", StringComparison.OrdinalIgnoreCase) ||
                name.Contains("Organisation", StringComparison.OrdinalIgnoreCase) ||
                name.Contains("Organization", StringComparison.OrdinalIgnoreCase) ||
                name.Contains("Entra", StringComparison.OrdinalIgnoreCase) ||
                name.Contains("DisplayName", StringComparison.OrdinalIgnoreCase))
            .ToArray();

        Assert.True(
            identifying.Length == 0,
            "The platform rollup names an organisation:\n  " + string.Join("\n  ", identifying));
    }

    [Fact]
    public void The_platform_rollup_exposes_no_per_organisation_collection()
    {
        // A breakdown is a disclosure wearing a chart. Any collection-valued member here would be
        // one, whatever it was called.
        PropertyInfo[] collections = typeof(DashboardRollup)
            .GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Where(property => property.PropertyType != typeof(string))
            .Where(property => typeof(System.Collections.IEnumerable).IsAssignableFrom(property.PropertyType))
            .ToArray();

        Assert.True(
            collections.Length == 0,
            "The platform rollup exposes a breakdown:\n  " +
            string.Join("\n  ", collections.Select(property => property.Name)));
    }

    [Fact]
    public void The_dashboard_read_surface_returns_a_single_aggregate()
    {
        // One aggregate, not a sequence of them. A method returning many rollups would leave the
        // caller to aggregate, and the caller is an endpoint that would serialise whatever it got.
        MethodInfo read = typeof(Modules.Tenancy.IDashboardReadModel)
            .GetMethod(nameof(Modules.Tenancy.IDashboardReadModel.GetPlatformAsync))!;

        Assert.Equal(typeof(Task<DashboardRollup?>), read.ReturnType);

        // And it takes no organisation parameter, so there is no "show me that one" to call.
        Assert.Equal([typeof(CancellationToken)], read.GetParameters().Select(p => p.ParameterType));
    }

    [Fact]
    public void Credential_material_reaches_no_read_contract()
    {
        // No credential material, ever — not values, not Key Vault references (contracts
        // §read-views rule 2). tenant_entitlement has no published view for this reason, so the
        // assertion is that no read contract grew a field that would carry one.
        string[] forbidden = ["secret", "password", "credential", "token", "apikey", "connectionstring"];

        List<string> offending = [];

        foreach (Type contract in typeof(DashboardRollup).Assembly
            .GetTypes()
            .Where(type => type.Namespace == typeof(DashboardRollup).Namespace))
        {
            foreach (PropertyInfo property in contract.GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                string name = property.Name.ToLowerInvariant();

                if (Array.Exists(forbidden, term => name.Contains(term, StringComparison.Ordinal)))
                {
                    offending.Add($"{contract.Name}.{property.Name}");
                }
            }
        }

        Assert.True(
            offending.Count == 0,
            "A read contract carries credential-shaped material:\n  " + string.Join("\n  ", offending));
    }
}
