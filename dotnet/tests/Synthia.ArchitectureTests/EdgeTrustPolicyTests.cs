using System.Text.Json;
using Synthia.SharedKernel.Identity;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The edge trust boundary, asserted against the shared registry (constitution Principle I).
/// </summary>
/// <remarks>
/// <para>
/// <b>The rule is cross-platform and the registry is shared.</b> <c>build/policy/edge-trust.json</c>
/// defines the only path by which an application API request may reach a backend, and the controls
/// that make that path provable rather than merely intended. RagCore enforces the same file from
/// <c>ragcore/tests/security/test_edge_trust_policy.py</c>, and the parity tests at the bottom of
/// each file assert the two agree — because two hand-maintained lists drift, and the drift is
/// invisible until the day the weaker of the two is the one that mattered.
/// </para>
/// <para>
/// <b>Structural, not runtime.</b> These read source and configuration rather than deploying
/// anything, so the rule holds in CI without an Azure subscription, and a failure names the file
/// and the construct instead of surfacing as a 403 in an environment somebody has to reproduce.
/// The behavioural half lives in <c>Synthia.ContractTests.GatewayProvenanceTests</c>, which poses
/// the attack against the real pipeline.
/// </para>
/// </remarks>
public sealed class EdgeTrustPolicyTests
{
    private static DirectoryInfo RepositoryRoot()
    {
        DirectoryInfo? root = ProjectGraph.SolutionDirectory().Parent;

        Assert.True(
            root is not null,
            "Could not locate the repository root above the solution directory. The shared edge " +
            "trust policy lives at build/policy/edge-trust.json and both stacks read it.");

        return root!;
    }

    private static string RepositoryPath(params string[] segments) =>
        Path.Combine([RepositoryRoot().FullName, .. segments]);

    private static JsonDocument Policy()
    {
        FileInfo file = new(RepositoryPath("build", "policy", "edge-trust.json"));

        Assert.True(
            file.Exists,
            "The shared edge trust policy is missing: " + file.FullName +
            ". Both deployables read this one file; without it neither rule enforces anything.");

        return JsonDocument.Parse(File.ReadAllText(file.FullName));
    }

    private static List<string> StringsFrom(JsonElement array) =>
        array.EnumerateArray().Select(element => element.GetString() ?? string.Empty).ToList();

    /// <summary>Asserts a production file declares a construct verbatim.</summary>
    /// <param name="declaration">The exact declaration expected.</param>
    /// <param name="fileName">The file that must carry it, for the failure message.</param>
    private static void AssertDeclaredInProduction(string declaration, string fileName)
    {
        IReadOnlyList<string> files = SourceTree.ProductionFilesContaining(declaration);

        Assert.True(
            files.Contains(fileName),
            $"{fileName} does not declare `{declaration}`. The shared edge trust policy and the "
            + "code that enforces it have drifted, and the drift is invisible until the day the "
            + "weaker of the two is the one that mattered.");
    }

    // ----------------------------------------------------------------------------------------
    // The contract the policy defines, and the code that consumes it
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void The_identity_contract_is_closed_and_matches_the_policy()
    {
        // CLOSED MEANS FIVE, EXACTLY. A sixth header carrying authority is a second identity
        // derivation wearing a different name. Asserting the count as well as the membership is
        // what makes adding one require editing the shared file rather than editing one service.
        using JsonDocument policy = Policy();
        JsonElement contract = policy.RootElement.GetProperty("identityContract");

        List<string> declared = StringsFrom(contract.GetProperty("headers"));

        Assert.True(contract.GetProperty("closed").GetBoolean());
        Assert.Equal(5, declared.Count);

        string[] implemented =
        [
            IdentityHeaders.TenantId,
            IdentityHeaders.PrincipalId,
            IdentityHeaders.Roles,
            IdentityHeaders.CredentialClass,
            IdentityHeaders.ClientSurface,
        ];

        Assert.Equal(
            declared.Order(StringComparer.Ordinal),
            implemented.Order(StringComparer.Ordinal));
    }

    [Fact]
    public void The_provenance_header_this_service_reads_is_the_one_the_policy_names()
    {
        // Two ends of one wire. If APIM stamps a header this service does not read, every request
        // is refused; if this service reads a header APIM does not stamp, nothing is checked. The
        // second failure is silent, which is why it is asserted rather than trusted.
        using JsonDocument policy = Policy();

        string declared = policy.RootElement
            .GetProperty("gatewayCertificate")
            .GetProperty("forwardedAs")
            .GetString() ?? string.Empty;

        // Asserted against the declaration in source rather than against the constant, because
        // this suite has no InternalsVisibleTo into Synthia.Api - by design. Its rules are about
        // what somebody wrote, and a compiled constant loses the distinction between a value that
        // was declared here and one that arrived from somewhere else.
        AssertDeclaredInProduction(
            $"public const string ForwardedClientCertificateHeader = \"{declared}\";",
            "GatewayProvenanceMiddleware.cs");
    }

    [Fact]
    public void The_exempt_paths_this_service_serves_are_the_ones_the_policy_names()
    {
        // The exemption list is the softest part of the whole arrangement - it is the one place
        // where "served without provenance" is the correct answer - so it is the part most worth
        // pinning to a file two people have to agree on.
        using JsonDocument policy = Policy();

        List<string> declared = StringsFrom(
            policy.RootElement.GetProperty("provenanceExempt").GetProperty("pathPrefixes"));

        // One prefix, and the service declares that one. More than one in the policy would mean a
        // second exemption nobody had implemented - which reads, in the file, as though it were
        // already enforced.
        Assert.Single(declared);

        AssertDeclaredInProduction(
            $"public const string ExemptPathPrefix = \"{declared[0]}\";",
            "GatewayProvenanceMiddleware.cs");
    }

    [Fact]
    public void The_allow_list_setting_name_matches_the_policy()
    {
        // A deployment sets the name the policy documents. A rename on one side and not the other
        // produces a process that fails to start, which is the good failure - but only if somebody
        // notices before the pipeline is written against the wrong name.
        using JsonDocument policy = Policy();

        string declared = policy.RootElement
            .GetProperty("gatewayCertificate")
            .GetProperty("allowListSetting")
            .GetProperty("dotnet")
            .GetString() ?? string.Empty;

        string[] parts = declared.Split("__");

        Assert.Equal(2, parts.Length);

        AssertDeclaredInProduction(
            $"public const string SectionName = \"{parts[0]}\";",
            "EdgeTrustOptions.cs");

        AssertDeclaredInProduction(
            $"public string {parts[1]} {{ get; init; }}",
            "EdgeTrustOptions.cs");
    }

    // ----------------------------------------------------------------------------------------
    // The rules the policy states about backend source
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void No_production_source_parses_a_token()
    {
        // Identity is derived exactly once, at the Gateway. A backend that could validate a token
        // would be a SECOND derivation point - and the second one is the one nobody audits.
        //
        // Read over comment-stripped source, so the comment explaining the rule does not trip it.
        using JsonDocument policy = Policy();

        List<string> forbidden = StringsFrom(
            policy.RootElement
                .GetProperty("backendRules")
                .GetProperty("neverParseTokens")
                .GetProperty("forbiddenInProductionSource"));

        List<string> violations = [];

        foreach (string term in forbidden)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(term))
            {
                violations.Add($"{file} contains '{term}'");
            }
        }

        Assert.True(
            violations.Count == 0,
            "Production source parses or validates a token:\n  " + string.Join("\n  ", violations));
    }

    [Fact]
    public void No_production_source_calls_another_platform_service_directly()
    {
        // Every application API call traverses the edge and the Gateway (spec 13.4). A private
        // peer route would be a second path into a backend - one where identity is whatever the
        // caller felt like sending, because no gateway re-established it.
        using JsonDocument policy = Policy();

        List<string> forbidden = StringsFrom(
            policy.RootElement
                .GetProperty("backendRules")
                .GetProperty("noDirectServiceToService")
                .GetProperty("forbiddenInProductionSource"));

        List<string> violations = [];

        foreach (string term in forbidden)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(term))
            {
                violations.Add($"{file} contains '{term}'");
            }
        }

        Assert.True(
            violations.Count == 0,
            "Production source addresses another platform service directly:\n  "
            + string.Join("\n  ", violations));
    }

    // ----------------------------------------------------------------------------------------
    // The deployed shape the policy requires
    // ----------------------------------------------------------------------------------------

    [Fact]
    public void No_container_app_declares_external_ingress()
    {
        // The network half of the apim-to-backend hop. External ingress on an application container
        // app IS the bypass the whole edge model exists to prevent, and it is one line in a YAML
        // file that reviews well and deploys quietly.
        DirectoryInfo manifests = new(RepositoryPath("build", "docker", "containerapps"));

        Assert.True(manifests.Exists, "Container app manifests are missing: " + manifests.FullName);

        List<string> violations = [];

        foreach (FileInfo manifest in manifests.GetFiles("*.yaml", SearchOption.AllDirectories))
        {
            foreach (string line in File.ReadAllLines(manifest.FullName))
            {
                string code = line.Split('#')[0].Trim();

                if (code.Replace(" ", string.Empty, StringComparison.Ordinal) == "external:true")
                {
                    violations.Add(manifest.Name);
                }
            }
        }

        Assert.True(
            violations.Count == 0,
            "A container app declares external ingress, which is a path around APIM:\n  "
            + string.Join("\n  ", violations));
    }

    [Fact]
    public void Every_container_app_serving_ingress_requires_a_client_certificate()
    {
        // The application half. Internal ingress alone admits everything already inside the VNet -
        // a compromised sidecar, a misconfigured job, a second container app - and each of those
        // could otherwise mint any tenant and any role it liked.
        //
        // `accept` is specifically not enough: it forwards a certificate when one is offered and
        // nothing when one is not, so an unauthenticated caller looks exactly like a correctly
        // configured one that has not been given a certificate yet.
        //
        // SCOPED TO APPS THAT SERVE INGRESS. A worker - a Service Bus consumer, a sweep - dials OUT
        // over AMQP as a managed identity and accepts no inbound request, so there is no connection
        // for a client certificate to appear on. Requiring it there would fail the first correctly
        // written worker manifest, and a rule that fires on correct code is one that gets skipped.
        DirectoryInfo manifests = new(RepositoryPath("build", "docker", "containerapps"));

        List<string> violations = [];

        foreach (FileInfo manifest in manifests.GetFiles("*.yaml", SearchOption.AllDirectories))
        {
            List<string> code = File.ReadAllLines(manifest.FullName)
                .Select(line => line.Split('#')[0].Trim())
                .ToList();

            if (!code.Contains("ingress:"))
            {
                continue;
            }

            if (!code.Contains("clientCertificateMode: require"))
            {
                violations.Add(manifest.Name);
            }
        }

        Assert.True(
            violations.Count == 0,
            "A container app serving ingress does not require a gateway client certificate:\n  "
            + string.Join("\n  ", violations));
    }

    [Fact]
    public void The_gateway_certificate_is_referenced_in_a_way_that_survives_rotation()
    {
        // A KEY VAULT CERTIFICATE'S THUMBPRINT CHANGES WHEN IT IS ROTATED, and an APIM policy that
        // identifies it by thumbprint silently fails to resolve the new one - it stops attaching a
        // client certificate at all. There is no error at the gateway; it surfaces as every backend
        // call losing provenance at the same moment.
        //
        // Asserted rather than reviewed because the broken spelling is the one that looks more
        // precise, and because it works perfectly until the day it does not.
        string xml = File.ReadAllText(RepositoryPath("build", "infra", "apim", "global.inbound.xml"));

        Assert.DoesNotContain("<authentication-certificate thumbprint=", xml, StringComparison.Ordinal);
        Assert.Contains("<authentication-certificate certificate-id=", xml, StringComparison.Ordinal);
    }

    [Fact]
    public void Rotation_is_deliberate_and_expiry_is_monitored()
    {
        // THESE TWO ARE ADOPTED TOGETHER OR NOT AT ALL.
        //
        // Pinning the Key Vault version stops an automatic four-hour sync from rotating the
        // certificate out from under a backend allow-list that pins the leaf hash - which would be
        // an unattended, total outage with no deployment behind it.
        //
        // But pinning the version also means nothing renews the certificate on our behalf any more,
        // which turns expiry from a background concern into the residual risk of the whole design.
        // A policy declaring one without the other is declaring half a control.
        using JsonDocument policy = Policy();
        JsonElement certificate = policy.RootElement.GetProperty("gatewayCertificate");
        JsonElement rotation = certificate.GetProperty("rotation");

        Assert.Equal("pinned-version", rotation.GetProperty("strategy").GetString());
        Assert.True(rotation.GetProperty("automaticSyncDisabled").GetBoolean());

        string runbook = rotation.GetProperty("runbook").GetString() ?? string.Empty;

        Assert.True(
            File.Exists(RepositoryPath(runbook.Split('/'))),
            $"The rotation runbook is missing: {runbook}. Rotation here is a sequenced manual "
            + "release - widen the allow-list, then switch the certificate - and the order IS the "
            + "control. An unwritten sequence is one somebody performs backwards under pressure.");

        JsonElement expiry = certificate.GetProperty("expiryMonitoring");

        Assert.True(expiry.GetProperty("required").GetBoolean());
        Assert.True(expiry.GetProperty("alertLeadTimeDays").GetInt32() >= 30);
    }

    [Fact]
    public void Expiry_monitoring_is_provisioned_and_not_merely_declared()
    {
        // A POLICY THAT DECLARES MONITORING WITHOUT INFRASTRUCTURE PROVIDING IT IS WORSE THAN
        // NEITHER, because the declaration is what stops somebody checking. This asserts the
        // alerting exists as committed infrastructure, not as an intention.
        using JsonDocument policy = Policy();
        JsonElement expiry = policy.RootElement
            .GetProperty("gatewayCertificate")
            .GetProperty("expiryMonitoring");

        string definedIn = expiry.GetProperty("definedIn").GetString() ?? string.Empty;
        FileInfo alerts = new(RepositoryPath(definedIn.Split('/')));

        Assert.True(alerts.Exists, $"The expiry alerting is missing: {definedIn}");

        using JsonDocument alerting = JsonDocument.Parse(File.ReadAllText(alerts.FullName));

        List<string> eventTypes = [];
        List<string> severitiesWithoutActionGroup = [];

        foreach (JsonElement subscription in alerting.RootElement.GetProperty("eventSubscriptions").EnumerateArray())
        {
            eventTypes.AddRange(
                StringsFrom(subscription.GetProperty("filter").GetProperty("includedEventTypes")));

            JsonElement destination = subscription.GetProperty("destination").GetProperty("properties");

            // An alert nobody is paged by is a dashboard.
            if (!destination.TryGetProperty("actionGroups", out JsonElement groups)
                || groups.GetArrayLength() == 0)
            {
                severitiesWithoutActionGroup.Add(subscription.GetProperty("name").GetString() ?? "?");
            }
        }

        Assert.Contains("Microsoft.KeyVault.CertificateNearExpiry", eventTypes);
        Assert.Contains("Microsoft.KeyVault.CertificateExpired", eventTypes);

        Assert.True(
            severitiesWithoutActionGroup.Count == 0,
            "An expiry alert reaches no action group, so it notifies nobody:\n  "
            + string.Join("\n  ", severitiesWithoutActionGroup));
    }

    [Fact]
    public void The_paging_lead_time_is_recorded_separately_from_the_earliest_notice()
    {
        // TWO LEAD TIMES, BECAUSE AZURE GIVES US NO CHOICE. The certificate near-expiry event is
        // fixed at 30 days and exposes no setting; only the KEY near-expiry event is configurable.
        // So the earliest we can be TOLD is 45 days, by a Key Vault lifetime action, over email -
        // and the earliest we can be WOKEN is 30.
        //
        // Both are recorded because collapsing them to the friendlier number would be a lie an
        // operator plans around: email is the weaker mechanism, and one holiday period consumes the
        // whole difference. The 30-day page is the real deadline.
        using JsonDocument policy = Policy();
        JsonElement expiry = policy.RootElement
            .GetProperty("gatewayCertificate")
            .GetProperty("expiryMonitoring");

        int paging = expiry.GetProperty("pagingLeadTimeDays").GetInt32();

        Assert.True(paging >= 30);
        Assert.True(expiry.GetProperty("alertLeadTimeDays").GetInt32() >= paging);

        // At least one channel must actually page, and the expiry channel must be among them.
        List<JsonElement> channels = [.. expiry.GetProperty("channels").EnumerateArray()];

        Assert.Contains(channels, channel => channel.GetProperty("pages").GetBoolean());

        Assert.Contains(
            channels,
            channel => channel.GetProperty("leadTimeDays").GetInt32() == 0
                && channel.GetProperty("pages").GetBoolean());
    }

    [Fact]
    public void The_gateway_deletes_every_inbound_copy_of_the_contract()
    {
        // THE OTHER END OF THE ANTI-SPOOFING CONTROL. This service refuses a request that cannot
        // prove provenance; APIM deletes any inbound copy of the contract before validating
        // anything. Neither is sufficient alone, and this asserts the half that lives outside the
        // application - where no compiler and no test would otherwise look.
        using JsonDocument policy = Policy();

        List<string> headers = StringsFrom(
            policy.RootElement.GetProperty("identityContract").GetProperty("headers"));

        FileInfo apimPolicy = new(RepositoryPath("build", "infra", "apim", "global.inbound.xml"));

        Assert.True(apimPolicy.Exists, "The APIM global policy is missing: " + apimPolicy.FullName);

        string xml = File.ReadAllText(apimPolicy.FullName);

        List<string> missing = headers
            .Where(header =>
                !xml.Contains($"<set-header name=\"{header}\" exists-action=\"delete\" />", StringComparison.Ordinal))
            .ToList();

        Assert.True(
            missing.Count == 0,
            "The APIM global policy does not delete an inbound copy of:\n  "
            + string.Join("\n  ", missing));

        // The forwarded certificate is the more dangerous of the two: a caller who could set it
        // would be asserting gateway provenance itself, which every other control rests on.
        Assert.Contains(
            "<set-header name=\"X-Forwarded-Client-Cert\" exists-action=\"delete\" />",
            xml,
            StringComparison.Ordinal);
    }

    [Fact]
    public void The_gateway_checks_the_front_door_identifier()
    {
        // The frontdoor-to-apim hop. The AzureFrontDoor.Backend service tag admits EVERY Azure
        // customer's Front Door, so an attacker provisions their own profile and points it at this
        // origin. The FDID check is what makes the origin specific to this platform.
        FileInfo apimPolicy = new(RepositoryPath("build", "infra", "apim", "global.inbound.xml"));

        string xml = File.ReadAllText(apimPolicy.FullName);

        Assert.Contains("X-Azure-FDID", xml, StringComparison.Ordinal);

        // A named value, never a literal. A literal here is an identifier committed to the
        // repository and pinned to one environment, which makes staging and production differ in
        // the one place they must not.
        Assert.Contains("{{front-door-id}}", xml, StringComparison.Ordinal);
    }

    [Fact]
    public void Every_audience_has_a_gateway_policy_that_derives_identity()
    {
        // The surface decides which authorization model applies (constitution Principle II), and
        // the surface is the route. One policy per audience is what makes that structural: there is
        // no shared branch in which the customer path could read a role claim.
        using JsonDocument policy = Policy();

        List<string> violations = [];

        foreach (JsonElement audience in policy.RootElement.GetProperty("audiences").EnumerateArray())
        {
            string id = audience.GetProperty("id").GetString() ?? string.Empty;
            string credentialClass = audience.GetProperty("credentialClass").GetString() ?? string.Empty;

            FileInfo file = new(RepositoryPath("build", "infra", "apim", $"{id}.v1.xml"));

            if (!file.Exists)
            {
                violations.Add($"{id}: no APIM policy at {file.FullName}");
                continue;
            }

            string xml = File.ReadAllText(file.FullName);

            if (!xml.Contains("<validate-azure-ad-token", StringComparison.Ordinal))
            {
                violations.Add($"{id}: the policy validates no token, so identity is never derived");
            }

            if (!xml.Contains($"<value>{credentialClass}</value>", StringComparison.Ordinal))
            {
                violations.Add($"{id}: the policy does not state the credential class '{credentialClass}'");
            }
        }

        Assert.True(
            violations.Count == 0,
            "An audience has no gateway policy deriving its identity:\n  "
            + string.Join("\n  ", violations));
    }

    [Fact]
    public void The_customer_gateway_policy_never_reads_a_role_claim()
    {
        // Any person acting on a customer surface is an end user, INCLUDING STAFF, and their staff
        // roles must not be consulted there (constitution Principle II). This is the one place a
        // person could promote themselves by holding a role elsewhere, so the absence is asserted
        // rather than reviewed.
        string xml = File.ReadAllText(RepositoryPath("build", "infra", "apim", "customer.v1.xml"));

        Assert.DoesNotContain("Claims[\"roles\"]", xml, StringComparison.Ordinal);
        Assert.DoesNotContain("Synthia_Admins", xml, StringComparison.Ordinal);
        Assert.DoesNotContain("Synthia_Agents", xml, StringComparison.Ordinal);
        Assert.Contains("<value>end_user</value>", xml, StringComparison.Ordinal);
    }

    [Fact]
    public void Front_door_publishes_exactly_one_origin_and_it_is_the_gateway()
    {
        // A second origin here would be a public route to a backend that looks, in the portal, like
        // a routing entry. It is the cheapest possible bypass of the entire trust boundary.
        FileInfo file = new(RepositoryPath("build", "infra", "frontdoor", "front-door.json"));

        Assert.True(file.Exists, "The Front Door definition is missing: " + file.FullName);

        using JsonDocument frontDoor = JsonDocument.Parse(File.ReadAllText(file.FullName));

        JsonElement originGroups = frontDoor.RootElement.GetProperty("originGroups");

        Assert.Equal(1, originGroups.GetArrayLength());

        JsonElement origins = originGroups[0].GetProperty("origins");

        Assert.Equal(1, origins.GetArrayLength());
        Assert.Equal("apim-gateway", origins[0].GetProperty("name").GetString());

        // Private Link, so APIM has no public ingress at all.
        Assert.True(origins[0].TryGetProperty("sharedPrivateLinkResource", out _));
    }
}
