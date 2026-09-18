using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Routing;
using Synthia.SharedKernel.Identity;

namespace Synthia.ContractTests;

/// <summary>
/// The conventions binding every endpoint (T066).
/// </summary>
/// <remarks>
/// These are asserted against the running application rather than read off the source, because the
/// conventions are properties of what goes on the wire. A route named correctly but serialised in
/// PascalCase still breaks every client.
/// </remarks>
public sealed class ApiConventionTests : IClassFixture<WebApplicationFixture>
{
    private readonly WebApplicationFixture _fixture;

    public ApiConventionTests(WebApplicationFixture fixture)
    {
        ArgumentNullException.ThrowIfNull(fixture);

        _fixture = fixture;
    }

    [Fact]
    public void Every_route_is_versioned_by_uri_segment()
    {
        // URI-segment versioning. A breaking change adds /v2/; it never mutates /v1/
        // (contracts §README). Asserted over the routing table so a route added without a version
        // fails here rather than at the first client that assumed one.
        List<string> unversioned = _fixture.ApiRoutes()
            .Where(route => !route.Contains("/v1/", StringComparison.Ordinal))
            .ToList();

        Assert.True(
            unversioned.Count == 0,
            "An API route carries no version segment:\n  " + string.Join("\n  ", unversioned));
    }

    [Fact]
    public void Every_route_sits_under_a_known_audience()
    {
        // The surface decides which authorization model applies (constitution Principle II), and
        // the surface is the route prefix. A route outside these prefixes would be authorized by
        // nothing, because IdentityContextMiddleware would not recognise it as an audience.
        string[] prefixes = ["/api/customer/v1", "/api/staff/v1", "/api/workload/v1"];

        List<string> orphaned = _fixture.ApiRoutes()
            .Where(route => !Array.Exists(prefixes, prefix => route.StartsWith(prefix, StringComparison.Ordinal)))
            .ToList();

        Assert.True(
            orphaned.Count == 0,
            "An API route sits outside every known audience:\n  " + string.Join("\n  ", orphaned));
    }

    [Fact]
    public void Every_route_segment_is_lower_case_or_kebab_case()
    {
        // Plural resource nouns, kebab-case for multi-word segments (contracts §README). An
        // upper-case letter in a literal segment is the tell for a camelCase route slipping in.
        List<string> offending = [];

        foreach (string route in _fixture.ApiRoutes())
        {
            foreach (string segment in route.Split('/', StringSplitOptions.RemoveEmptyEntries))
            {
                if (segment.StartsWith('{'))
                {
                    continue;
                }

                if (segment.Any(char.IsUpper))
                {
                    offending.Add($"{route} -> {segment}");
                }
            }
        }

        Assert.True(
            offending.Count == 0,
            "A literal route segment is not lower-case or kebab-case:\n  " + string.Join("\n  ", offending));
    }

    [Fact]
    public async Task A_problem_response_is_rfc_9457_and_carries_a_correlation_id()
    {
        using HttpClient client = _fixture.CreateClient();

        // No identity headers at all. The request is refused before it can reach anything.
        using HttpResponseMessage response = await client.GetAsync(
            new Uri("/api/customer/v1/views/sessions", UriKind.Relative));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);

        JsonElement problem = await response.Content.ReadFromJsonAsync<JsonElement>();

        // RFC 9457 members, plus the correlation identifier that makes a user-visible error
        // traceable across a suspendable, asynchronous flow (contracts §README).
        Assert.True(problem.TryGetProperty("type", out _));
        Assert.True(problem.TryGetProperty("title", out _));
        Assert.True(problem.TryGetProperty("status", out _));
        Assert.True(problem.TryGetProperty("correlationId", out JsonElement correlationId));
        Assert.False(string.IsNullOrWhiteSpace(correlationId.GetString()));

        // Nothing internal leaks: no stack trace, no exception type, no connection string.
        string body = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("Exception", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("   at ", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_correlation_id_is_echoed_on_every_response()
    {
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await client.GetAsync(new Uri("/health/live", UriKind.Relative));

        Assert.True(response.Headers.TryGetValues("X-Correlation-Id", out IEnumerable<string>? values));
        Assert.False(string.IsNullOrWhiteSpace(values!.FirstOrDefault()));
    }

    [Fact]
    public async Task A_well_formed_correlation_id_is_accepted_unchanged()
    {
        using HttpClient client = _fixture.CreateClient();

        CorrelationId supplied = CorrelationId.New();

        using HttpRequestMessage request = new(HttpMethod.Get, new Uri("/health/live", UriKind.Relative));
        request.Headers.Add("X-Correlation-Id", supplied.Value);

        using HttpResponseMessage response = await client.SendAsync(request);

        Assert.Equal(supplied.Value, response.Headers.GetValues("X-Correlation-Id").Single());
    }

    [Fact]
    public async Task A_malformed_correlation_id_is_replaced_rather_than_echoed()
    {
        // Accepted only when well formed; generated when missing or invalid (constitution
        // §Correlation). Echoing an arbitrary client string back would make the header a reflection
        // point, and a log-injection vector one hop later.
        using HttpClient client = _fixture.CreateClient();

        using HttpRequestMessage request = new(HttpMethod.Get, new Uri("/health/live", UriKind.Relative));
        request.Headers.Add("X-Correlation-Id", "not a correlation id");

        using HttpResponseMessage response = await client.SendAsync(request);

        string echoed = response.Headers.GetValues("X-Correlation-Id").Single();

        Assert.NotEqual("not a correlation id", echoed);
        Assert.True(CorrelationId.TryAccept(echoed, out _));
    }

    [Fact]
    public async Task An_unknown_sort_field_is_a_400_and_names_what_is_allowed()
    {
        // An unknown field is a 400, never silently ignored (contracts §README). Silently ignoring
        // it is worse than failing: the client believes it sorted and receives another order.
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await StaffRequest(client, "/api/staff/v1/views/audit?sort=whenever");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);

        JsonElement problem = await response.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Contains("occurredAt", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task An_unknown_filter_field_is_a_400()
    {
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await StaffRequest(
            client,
            "/api/staff/v1/views/approvals/queue?somethingElse=1");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task An_unreadable_cursor_is_a_400_rather_than_a_silent_restart()
    {
        // Answering a tampered cursor with page one looks to a client exactly like the end of the
        // collection, which is the same shape as data loss.
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await StaffRequest(
            client,
            "/api/staff/v1/views/audit?cursor=!!!not-base64!!!");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task A_tenant_parameter_is_refused_on_the_customer_audience()
    {
        // No endpoint accepts a tenant, role or audience parameter and trusts it (contracts §README
        // rule 1). Refused at the edge, before an endpoint can be tempted to read one.
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await client.GetAsync(
            new Uri("/api/customer/v1/views/sessions?tenantId=" + Guid.NewGuid(), UriKind.Relative));

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task A_role_parameter_is_refused_on_every_audience()
    {
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage customer = await client.GetAsync(
            new Uri("/api/customer/v1/views/sessions?roles=administrator", UriKind.Relative));
        using HttpResponseMessage staff = await StaffRequest(
            client,
            "/api/staff/v1/views/audit?roles=administrator");

        Assert.Equal(HttpStatusCode.BadRequest, customer.StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, staff.StatusCode);
    }

    [Fact]
    public async Task The_openapi_document_describes_the_api_in_camel_case()
    {
        // ONE DOCUMENT PER AUDIENCE. There is deliberately no combined `/openapi/v1.json`: a
        // merged document would let a customer-facing client enumerate the staff surface. So this
        // asks each audience separately and asserts each carries only its own paths, which is a
        // stronger statement than the combined document could make.
        using HttpClient client = _fixture.CreateClient();

        foreach (string audience in new[] { "customer", "staff" })
        {
            using HttpResponseMessage response = await client.GetAsync(
                new Uri($"/openapi/{audience}.json", UriKind.Relative));

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);

            JsonElement document = await response.Content.ReadFromJsonAsync<JsonElement>();
            JsonElement paths = document.GetProperty("paths");

            Assert.Contains(
                paths.EnumerateObject(),
                path => path.Name.StartsWith($"/api/{audience}/v1/views", StringComparison.Ordinal));

            Assert.DoesNotContain(
                paths.EnumerateObject(),
                path => !path.Name.StartsWith($"/api/{audience}/v1", StringComparison.Ordinal));
        }
    }

    private static async Task<HttpResponseMessage> StaffRequest(HttpClient client, string path)
    {
        using HttpRequestMessage request = new(HttpMethod.Get, new Uri(path, UriKind.Relative));

        StaffHeaders.Apply(request, "technician");

        return await client.SendAsync(request);
    }
}

/// <summary>
/// The Gateway-derived headers a staff request arrives with.
/// </summary>
/// <remarks>
/// Written out here rather than produced by the application, because a contract test that used the
/// application's own header builder would pass even if the header contract changed underneath it.
/// </remarks>
internal static class StaffHeaders
{
    public static void Apply(HttpRequestMessage request, params string[] roles)
    {
        // Roles arrive in canonical ascending order — checked at the boundary, not assumed, because
        // "token array order never decides anything" has to be verifiable.
        request.Headers.Add(IdentityHeaders.TenantId, Guid.NewGuid().ToString("D"));
        request.Headers.Add(IdentityHeaders.PrincipalId, Guid.NewGuid().ToString("D"));
        request.Headers.Add(IdentityHeaders.Roles, string.Join(',', roles.Order(StringComparer.Ordinal)));
        request.Headers.Add(IdentityHeaders.CredentialClass, "delegated");
        request.Headers.Add(IdentityHeaders.ClientSurface, "contract-tests");
    }
}

/// <summary>Shares one booted application across the contract suite.</summary>
public sealed class WebApplicationFixture : IDisposable
{
    private readonly SynthiaApiFactory _factory = new();

    /// <summary>Creates a client against the running application.</summary>
    /// <remarks>
    /// It carries no gateway-provenance marker, because the application no longer looks for one:
    /// that mechanism is deferred (ADR 0008) and was not replaced. Every caller now reaches the
    /// pipeline the same way, which is itself the consequence the ADR records.
    /// </remarks>
    /// <returns>The client.</returns>
    public HttpClient CreateClient() => _factory.CreateClient();

    /// <summary>The literal patterns of every mapped API route.</summary>
    /// <returns>Route patterns under <c>/api</c>.</returns>
    public IReadOnlyList<string> ApiRoutes() =>
        _factory.Services.GetRequiredService<EndpointDataSource>()
            .Endpoints
            .OfType<RouteEndpoint>()
            .Select(endpoint => "/" + endpoint.RoutePattern.RawText?.TrimStart('/'))
            .Where(route => route.StartsWith("/api", StringComparison.Ordinal))
            .Distinct(StringComparer.Ordinal)
            .ToList();

    /// <inheritdoc/>
    public void Dispose() => _factory.Dispose();
}
