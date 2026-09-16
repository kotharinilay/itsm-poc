using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The monolith exposes no state-changing endpoint (T067).
/// </summary>
/// <remarks>
/// <para>
/// <b>RagCore owns every state-changing operation; the .NET modular monolith is read-only</b>
/// (ADR-0001, constitution Principle V, contracts §README rule 3). This walks the routing table the
/// application actually builds, so a <c>MapPost</c> added anywhere fails here rather than at review.
/// </para>
/// <para>
/// The rule is asserted over HTTP verbs rather than over method names because the verb is what a
/// client can reach. A handler called <c>UpdateThing</c> mapped to <c>GET</c> is a naming problem;
/// a handler called <c>GetThing</c> mapped to <c>POST</c> is a breach of the architecture.
/// </para>
/// </remarks>
public sealed class NoWriteEndpointTests : IClassFixture<RoutingTableFixture>
{
    private readonly RoutingTableFixture _routing;

    public NoWriteEndpointTests(RoutingTableFixture routing)
    {
        ArgumentNullException.ThrowIfNull(routing);

        _routing = routing;
    }

    [Fact]
    public void No_endpoint_accepts_a_state_changing_verb()
    {
        string[] stateChanging = ["POST", "PUT", "PATCH", "DELETE"];

        List<string> writes = [];

        foreach (RouteEndpoint endpoint in _routing.Endpoints)
        {
            HttpMethodMetadata? methods = endpoint.Metadata.GetMetadata<HttpMethodMetadata>();

            if (methods is null)
            {
                continue;
            }

            foreach (string verb in methods.HttpMethods)
            {
                if (Array.Exists(stateChanging, changing => string.Equals(verb, changing, StringComparison.Ordinal)))
                {
                    writes.Add($"{verb} {endpoint.RoutePattern.RawText}");
                }
            }
        }

        Assert.True(
            writes.Count == 0,
            "The read-only monolith exposes a state-changing endpoint. Every write belongs to " +
            "RagCore (ADR-0001):\n  " + string.Join("\n  ", writes));
    }

    [Fact]
    public void Every_api_endpoint_accepts_only_GET()
    {
        // The positive form. "No POST" would be satisfied by an endpoint mapped with MapMethods to
        // something exotic; "only GET" would not.
        List<string> offending = [];

        foreach (RouteEndpoint endpoint in _routing.Endpoints)
        {
            string pattern = endpoint.RoutePattern.RawText ?? string.Empty;

            if (!pattern.StartsWith("api/", StringComparison.Ordinal) &&
                !pattern.StartsWith("/api/", StringComparison.Ordinal))
            {
                continue;
            }

            HttpMethodMetadata? methods = endpoint.Metadata.GetMetadata<HttpMethodMetadata>();
            IReadOnlyList<string> verbs = methods?.HttpMethods ?? [];

            if (verbs.Count != 1 || !string.Equals(verbs[0], "GET", StringComparison.Ordinal))
            {
                offending.Add($"{pattern} -> [{string.Join(", ", verbs)}]");
            }
        }

        Assert.True(
            offending.Count == 0,
            "An API endpoint accepts something other than GET:\n  " + string.Join("\n  ", offending));
    }

    [Fact]
    public void Every_view_route_sits_under_a_views_segment()
    {
        // The contracts split each audience: /api/{audience}/v1/... belongs to RagCore and
        // /api/{audience}/v1/views/... belongs here. A route outside the views segment would be
        // this deployable claiming part of RagCore's surface.
        List<string> offending = _routing.Endpoints
            .Select(endpoint => endpoint.RoutePattern.RawText ?? string.Empty)
            .Where(pattern => pattern.StartsWith("api/", StringComparison.Ordinal))
            .Where(pattern => !pattern.Contains("/views", StringComparison.Ordinal))
            .ToList();

        Assert.True(
            offending.Count == 0,
            "An API route sits outside the views segment this deployable owns:\n  " +
            string.Join("\n  ", offending));
    }
}

/// <summary>Builds the application once and exposes its routing table.</summary>
/// <remarks>
/// Boots the real application rather than reflecting over source text. The routing table is the
/// only place that knows what is genuinely reachable — including anything a library mapped.
/// </remarks>
public sealed class RoutingTableFixture : IDisposable
{
    private readonly ArchitectureApiFactory _factory = new();

    /// <summary>Every route endpoint the application maps.</summary>
    public IReadOnlyList<RouteEndpoint> Endpoints =>
        _factory.Services.GetRequiredService<EndpointDataSource>()
            .Endpoints
            .OfType<RouteEndpoint>()
            .ToList();

    /// <inheritdoc/>
    public void Dispose() => _factory.Dispose();
}
