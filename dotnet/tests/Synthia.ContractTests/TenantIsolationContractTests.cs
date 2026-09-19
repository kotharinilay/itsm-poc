using System.Net;
using Microsoft.Extensions.DependencyInjection;
using Synthia.Contracts.Paging;
using Synthia.Contracts.ReadModels;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;

namespace Synthia.ContractTests;

/// <summary>
/// A resource that is not the caller's answers <b>404</b> — never 403, never 200 (T161).
/// </summary>
/// <remarks>
/// <para>
/// 404 rather than 403 is the contract (contracts/customer-api.md): existence is itself
/// tenant-scoped information, and 403 tells a caller that the session they guessed is real.
/// </para>
/// <para>
/// <b>What this proves and what it does not.</b> The identity pipeline, the scope binding, the
/// routing and the endpoints are the real ones; only the store is stood in for, and it scopes by
/// the same <see cref="ITenantScope"/> that the EF global query filter binds. So this covers
/// identity → scope → query → status. That the filter cannot be escaped in SQL is a different
/// claim, asserted structurally in <c>Synthia.TenantIsolationTests</c>.
/// </para>
/// <para>
/// The suite used to assert neither: it checked that a filter predicate existed and that view rows
/// carry an organisation, and nothing ever exercised a read path or the 404.
/// </para>
/// </remarks>
public sealed class TenantIsolationContractTests
{
    private static readonly Guid _ownEntraTenant = new("22222222-2222-2222-2222-222222222222");
    private static readonly Guid _ownTenant = new("11111111-1111-1111-1111-111111111111");
    private static readonly Guid _otherTenant = new("44444444-4444-4444-4444-444444444444");
    private static readonly Guid _requester = new("33333333-3333-3333-3333-333333333333");
    private static readonly Guid _ownSession = new("aaaaaaaa-0000-0000-0000-000000000001");
    private static readonly Guid _otherOrganisationsSession = new("bbbbbbbb-0000-0000-0000-000000000002");
    private static readonly Guid _sameOrganisationAnotherUsersSession =
        new("cccccccc-0000-0000-0000-000000000003");

    private static HttpClient Client()
    {
        SynthiaApiFactory factory = new(services =>
        {
            services.AddScoped<ITenantRegistry, AdmittingRegistry>();
            services.AddScoped<ICustomerSessionReadModel, StoreStandIn>();
        });

        HttpClient client = factory.CreateClient();
        client.DefaultRequestHeaders.Add("X-Idp-Tenant-Id", _ownEntraTenant.ToString());
        client.DefaultRequestHeaders.Add("X-Idp-Principal-Id", _requester.ToString());
        client.DefaultRequestHeaders.Add("X-Idp-Roles", "end_user");
        client.DefaultRequestHeaders.Add("X-Idp-Credential-Class", "delegated");
        client.DefaultRequestHeaders.Add("X-Idp-Client-Surface", "web");
        return client;
    }

    /// <summary>The caller's own session is readable, so the negatives below mean something.</summary>
    [Fact]
    public async Task The_callers_own_session_is_returned()
    {
        using HttpClient client = Client();

        using HttpResponseMessage response = await client.GetAsync(
            new Uri($"/api/customer/v1/views/sessions/{_ownSession}", UriKind.Relative));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    /// <summary>Another organisation's session is indistinguishable from one that does not exist.</summary>
    [Theory]
    [InlineData("bbbbbbbb-0000-0000-0000-000000000002")]
    [InlineData("cccccccc-0000-0000-0000-000000000003")]
    [InlineData("dddddddd-0000-0000-0000-000000000004")]
    public async Task A_session_that_is_not_the_callers_is_not_found(string sessionId)
    {
        using HttpClient client = Client();

        using HttpResponseMessage response = await client.GetAsync(
            new Uri($"/api/customer/v1/views/sessions/{sessionId}", UriKind.Relative));

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
    }

    /// <summary>A listing returns the caller's own rows and no other organisation's.</summary>
    [Fact]
    public async Task A_listing_returns_only_the_callers_own_organisation()
    {
        using HttpClient client = Client();

        using HttpResponseMessage response = await client.GetAsync(
            new Uri("/api/customer/v1/views/sessions", UriKind.Relative));
        string body = await response.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains(_ownSession.ToString(), body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain(_otherTenant.ToString(), body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain(
            _otherOrganisationsSession.ToString(), body, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>Admits the one organisation these tests act as.</summary>
    private sealed class AdmittingRegistry : ITenantRegistry
    {
        public Task<TenantAdmissionRecord?> FindAsync(
            EntraTenantId entraTenantId, CancellationToken cancellationToken) =>
            Task.FromResult<TenantAdmissionRecord?>(
                entraTenantId.Value == _ownEntraTenant
                    ? new TenantAdmissionRecord(
                        new TenantId(_ownTenant), entraTenantId, TenantStatus.Active)
                    : null);
    }

    /// <summary>
    /// The store, scoping by the bound organisation and the requester exactly as the real queries do.
    /// </summary>
    private sealed class StoreStandIn : ICustomerSessionReadModel
    {
        private static readonly (Guid Session, Guid Tenant, Guid Requester)[] _rows =
        [
            (_ownSession, _ownTenant, _requester),
            (_otherOrganisationsSession, _otherTenant, _requester),
            (_sameOrganisationAnotherUsersSession, _ownTenant, Guid.NewGuid()),
        ];

        private readonly ITenantScope _scope;

        public StoreStandIn(ITenantScope scope) => _scope = scope;

        private IEnumerable<(Guid Session, Guid Tenant, Guid Requester)> Visible(PrincipalId requester)
        {
            Guid? organisation = _scope.Organisation?.TenantId.Value;
            return _rows.Where(row => row.Tenant == organisation && row.Requester == requester.Value);
        }

        private static SessionSummary Summary((Guid Session, Guid Tenant, Guid Requester) row) =>
            new(row.Session, row.Tenant, SessionState.Conversational, null,
                DateTimeOffset.UnixEpoch, DateTimeOffset.UnixEpoch, null);

        public Task<KeysetPage<SessionSummary>> ListAsync(
            PrincipalId requester,
            SessionListFilter filter,
            KeysetRequest request,
            CancellationToken cancellationToken) =>
            Task.FromResult(new KeysetPage<SessionSummary>(
                Visible(requester).Select(Summary).ToList(), null));

        public Task<SessionSummary?> FindAsync(
            PrincipalId requester, SessionId sessionId, CancellationToken cancellationToken)
        {
            (Guid Session, Guid Tenant, Guid Requester) row =
                Visible(requester).FirstOrDefault(candidate => candidate.Session == sessionId.Value);

            return Task.FromResult(row.Session == Guid.Empty ? null : Summary(row));
        }

        public Task<KeysetPage<SessionMessage>> ListMessagesAsync(
            PrincipalId requester,
            SessionId sessionId,
            SessionMessageFilter filter,
            KeysetRequest request,
            CancellationToken cancellationToken) =>
            throw new NotSupportedException("Not part of this contract.");

        public Task<IReadOnlyList<SessionStep>> ListStepsAsync(
            PrincipalId requester,
            SessionId sessionId,
            CancellationToken cancellationToken) =>
            throw new NotSupportedException("Not part of this contract.");
    }
}
