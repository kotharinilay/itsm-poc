using System.Text.Json;
using Synthia.SharedKernel.Identity;

namespace Synthia.ArchitectureTests;

/// <summary>
/// The edge trust boundary, asserted against the shared registry (A1 §4.5).
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
/// </para>
/// <para>
/// <b>There is no behavioural half any more.</b> It lived in
/// <c>Synthia.ContractTests.GatewayProvenanceTests</c> and posed the attack against the real
/// pipeline. That mechanism is deferred
/// (<c>docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md</c>) and nothing
/// replaced it, so the assertion stopped being true and the file was removed rather than softened
/// into one that passes.
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
    public void The_gateway_deletes_every_inbound_copy_of_the_contract()
    {
        // THE ANTI-SPOOFING CONTROL AT THE EDGE, and now the only one of its kind. APIM deletes
        // any inbound copy of the contract before validating anything, so a caller arriving from
        // the internet cannot smuggle one through the gateway.
        //
        // The backend-side half - refusing a request that could not prove gateway provenance - is
        // deferred (docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md) and
        // was not replaced, which makes this deletion load-bearing in a way it was not before.
        // It lives outside the application, where no compiler and no other test would look.
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
        // The surface decides which authorization model applies (A1 §6), and
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
        // roles must not be consulted there (A1 §6). This is the one place a
        // person could promote themselves by holding a role elsewhere, so the absence is asserted
        // rather than reviewed.
        string xml = File.ReadAllText(RepositoryPath("build", "infra", "apim", "customer.v1.xml"));

        Assert.DoesNotContain("Claims[\"roles\"]", xml, StringComparison.Ordinal);
        Assert.DoesNotContain("Synthia_Admins", xml, StringComparison.Ordinal);
        Assert.DoesNotContain("Synthia_Agents", xml, StringComparison.Ordinal);
        Assert.Contains("<value>end_user</value>", xml, StringComparison.Ordinal);
    }

    [Fact]
    public void Front_door_publishes_the_gateway_and_the_two_portals_and_nothing_else()
    {
        // An origin that is neither the gateway nor a portal bundle would be a public route to a
        // backend that looks, in the portal, like a routing entry. It is the cheapest possible
        // bypass of the entire trust boundary.
        //
        // An allow-list by name rather than a count (ADR-0009): a count passes a definition that
        // swapped one origin for another, which is the change worth catching.
        FileInfo file = new(RepositoryPath("build", "infra", "frontdoor", "front-door.json"));

        Assert.True(file.Exists, "The Front Door definition is missing: " + file.FullName);

        using JsonDocument frontDoor = JsonDocument.Parse(File.ReadAllText(file.FullName));

        JsonElement originGroups = frontDoor.RootElement.GetProperty("originGroups");

        Dictionary<string, JsonElement> groups = originGroups.EnumerateArray()
            .ToDictionary(group => group.GetProperty("name").GetString()!, group => group);

        Assert.Equal(
            ["apim", "customer-portal", "staff-portal"],
            groups.Keys.Order(StringComparer.Ordinal));

        Dictionary<string, string> expectedOrigin = new(StringComparer.Ordinal)
        {
            ["apim"] = "apim-gateway",
            ["customer-portal"] = "customer-portal-app",
            ["staff-portal"] = "staff-portal-app",
        };

        foreach ((string groupName, JsonElement group) in groups)
        {
            JsonElement origins = group.GetProperty("origins");

            Assert.Equal(1, origins.GetArrayLength());
            Assert.Equal(expectedOrigin[groupName], origins[0].GetProperty("name").GetString());

            // Private Link, so no target holds a public endpoint of its own — and the link must
            // NAME a resource rather than merely be present as a key.
            Assert.True(
                origins[0].TryGetProperty("sharedPrivateLinkResource", out JsonElement link),
                $"{groupName} is reachable without Private Link");
            Assert.False(
                string.IsNullOrWhiteSpace(link.GetProperty("privateLink").GetString()),
                $"{groupName} declares a Private Link that names no resource");
        }
    }

    [Fact]
    public void Only_the_gateway_origin_serves_an_api_path()
    {
        // The portals serve static files. One answering /api would reach the platform on a host
        // APIM never saw, which is the bypass the single gateway exists to prevent.
        FileInfo file = new(RepositoryPath("build", "infra", "frontdoor", "front-door.json"));

        using JsonDocument frontDoor = JsonDocument.Parse(File.ReadAllText(file.FullName));

        foreach (JsonElement route in frontDoor.RootElement.GetProperty("routes").EnumerateArray())
        {
            if (route.GetProperty("originGroup").GetString() == "apim")
            {
                continue;
            }

            foreach (JsonElement pattern in route.GetProperty("patternsToMatch").EnumerateArray())
            {
                Assert.False(
                    pattern.GetString()?.StartsWith("/api", StringComparison.Ordinal) ?? false,
                    $"edge route {route.GetProperty("name").GetString()} publishes an /api path "
                    + "on a portal origin");
            }
        }
    }
}
