using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Synthia.SharedKernel.Identity;

namespace Synthia.ContractTests;

/// <summary>
/// The edge trust boundary, asserted from the attacker's position (constitution Principle I).
/// </summary>
/// <remarks>
/// <para>
/// Every test here arrives the way something inside the network arrives: addressing the container
/// directly, free to send any header it likes. That is the threat the whole arrangement exists to
/// answer, and it is the one a test suite that only ever calls through a correctly configured
/// client never poses.
/// </para>
/// <para>
/// <b>These run against the real pipeline.</b> Nothing is stubbed and nothing is bypassed — a
/// provenance test against a rearranged pipeline proves nothing about provenance.
/// </para>
/// </remarks>
public sealed class GatewayProvenanceTests : IClassFixture<WebApplicationFixture>
{
    private const string CustomerPath = "/api/customer/v1/sessions";
    private const string StaffPath = "/api/staff/v1/sessions";

    /// <summary>A complete, well-formed identity context. Everything an attacker would send.</summary>
    /// <remarks>
    /// Deliberately valid. A forged context that failed on its own merits would let these tests
    /// pass for the wrong reason — the point is that a <i>perfect</i> forgery is still refused,
    /// because it is refused on provenance and never examined at all.
    /// </remarks>
    private static readonly (string Name, string Value)[] _forgedIdentity =
    [
        (IdentityHeaders.TenantId, "8f14e45f-ceea-467a-9b71-1d2e3c4b5a60"),
        (IdentityHeaders.PrincipalId, "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        (IdentityHeaders.Roles, "administrator"),
        (IdentityHeaders.CredentialClass, "delegated"),
        (IdentityHeaders.ClientSurface, "forged"),
    ];

    private readonly WebApplicationFixture _fixture;

    public GatewayProvenanceTests(WebApplicationFixture fixture)
    {
        ArgumentNullException.ThrowIfNull(fixture);

        _fixture = fixture;
    }

    [Theory]
    [InlineData(CustomerPath)]
    [InlineData(StaffPath)]
    public async Task A_request_that_did_not_traverse_the_gateway_is_refused(string path)
    {
        // THE CENTRAL ASSERTION. No forwarded certificate means the request did not come through
        // APIM, and nothing it carries is worth reading.
        using HttpClient client = _fixture.CreateDirectClient();

        using HttpResponseMessage response = await client.GetAsync(new Uri(path, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [InlineData(CustomerPath)]
    [InlineData(StaffPath)]
    public async Task A_forged_identity_context_is_refused_on_provenance(string path)
    {
        // The forgery is complete and well formed: a real tenant shape, a real principal shape, the
        // administrator role, the right credential class for the audience. It is refused anyway,
        // and refused BEFORE any of it is parsed - which is the property that matters. A service
        // that rejected this on some detail of the headers would still accept a better forgery.
        using HttpClient client = _fixture.CreateDirectClient();

        foreach ((string name, string value) in _forgedIdentity)
        {
            client.DefaultRequestHeaders.TryAddWithoutValidation(name, value);
        }

        using HttpResponseMessage response = await client.GetAsync(new Uri(path, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task A_certificate_from_another_holder_is_refused()
    {
        // The check is an ALLOW-LIST, not a format check. A well-formed hash belonging to somebody
        // else's certificate is exactly what a format check would wave through, and exactly what
        // an attacker with their own certificate would present.
        using HttpClient client = _fixture.CreateClientPresenting(FakeGateway.UnknownCertificateHash);

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [InlineData("")]
    [InlineData("Subject=\"CN=synthia-gateway\"")]
    [InlineData("Hash=")]
    [InlineData("Hash=deadbeef")]
    [InlineData("By=spiffe://cluster/gateway;Cert=\"-----BEGIN CERTIFICATE-----\"")]
    public async Task A_forwarded_certificate_without_a_usable_hash_is_refused(string headerValue)
    {
        // Every shape of "the header is present but says nothing". A truncated hash is included
        // because it is what a hand-edited or half-copied value looks like, and because accepting
        // a prefix match would turn a 64-character control into an 8-character one.
        using HttpClient client = _fixture.CreateClientSendingRaw(headerValue);

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task A_forwarded_chain_is_refused_even_when_it_contains_an_accepted_hash()
    {
        // Two elements means something between APIM and this process appended to the header. There
        // is no safe reading of that: taking the first trusts whatever was furthest away, taking
        // the last trusts whatever was nearest. An attacker who can append gets to choose which
        // rule is convenient, so the answer is to accept neither.
        string chain =
            FakeGateway.ForwardedClientCert(FakeGateway.UnknownCertificateHash)
            + ","
            + FakeGateway.ForwardedClientCert(FakeGateway.CertificateHash);

        using HttpClient client = _fixture.CreateClientSendingRaw(chain);

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task A_refusal_discloses_nothing_about_the_control()
    {
        // A problem document that named the header, the allow-list or which of the two checks
        // failed would describe the boundary to whoever is probing it - and an attacker who learns
        // WHICH check failed learns how close they got.
        using HttpClient client = _fixture.CreateClientPresenting(FakeGateway.UnknownCertificateHash);

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        string body = await response.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);

        foreach (string disclosure in new[]
                 {
                     "X-Forwarded-Client-Cert",
                     "thumbprint",
                     "Thumbprint",
                     "allow-list",
                     "certificate",
                     FakeGateway.CertificateHash,
                 })
        {
            Assert.DoesNotContain(disclosure, body, StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public async Task A_refusal_is_still_a_problem_document_carrying_a_correlation_id()
    {
        // Refusing at the edge must not cost the operator the thread. Provenance runs INSIDE
        // correlation for exactly this reason: a refusal a user can quote is one somebody can find.
        using HttpClient client = _fixture.CreateDirectClient();

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        Assert.True(response.Headers.Contains("X-Correlation-Id"));

        JsonElement problem = await response.Content.ReadFromJsonAsync<JsonElement>();

        Assert.Equal(403, problem.GetProperty("status").GetInt32());
        Assert.False(string.IsNullOrWhiteSpace(problem.GetProperty("correlationId").GetString()));
    }

    [Theory]
    [InlineData("/health/live")]
    [InlineData("/health/ready")]
    public async Task A_health_probe_is_served_without_provenance(string path)
    {
        // The probe comes from the Container Apps infrastructure on the internal network. It does
        // not traverse APIM, carries no certificate, and has nothing it could carry instead.
        //
        // This is the one exemption, and it is safe only because these paths expose no identity: a
        // caller reaching one has gained nothing it could not have guessed.
        using HttpClient client = _fixture.CreateDirectClient();

        using HttpResponseMessage response = await client.GetAsync(new Uri(path, UriKind.Relative));

        Assert.NotEqual(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task A_path_merely_beginning_with_health_is_not_exempt()
    {
        // The exemption is a SEGMENT prefix, not a string prefix. /healthcheck-bypass must not
        // inherit it - which is precisely the route somebody would add to get around this.
        using HttpClient client = _fixture.CreateDirectClient();

        using HttpResponseMessage response =
            await client.GetAsync(new Uri("/healthcheck-bypass", UriKind.Relative));

        Assert.NotEqual(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task A_gateway_routed_request_reaches_the_pipeline()
    {
        // The negative half of every test above: provenance must let the real thing through. A
        // control that refused everything would pass all the assertions here and serve nobody.
        //
        // 401 rather than 200 is the correct outcome - provenance was satisfied, so the request
        // reached IdentityContextMiddleware, which refused it for carrying no identity context.
        // That is the two layers doing their own jobs in the right order.
        using HttpClient client = _fixture.CreateClient();

        using HttpResponseMessage response = await client.GetAsync(new Uri(CustomerPath, UriKind.Relative));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
