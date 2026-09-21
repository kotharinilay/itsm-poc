using System.Reflection;
using Microsoft.AspNetCore.Http;

namespace Synthia.ArchitectureTests;

/// <summary>
/// Identity is derived once, at the Gateway, and this deployable only consumes it.
/// </summary>
/// <remarks>
/// <b>Services MUST NOT parse an access token</b> and consume only the closed Gateway-derived
/// header contract (A1 §4.5). A single derivation point is the only structure in
/// which authority can be audited and cannot be forged by a compromised surface.
/// </remarks>
public sealed class IdentityDisciplineTests
{
    [Fact]
    public void No_production_code_parses_a_token()
    {
        // Reading the header is the first step of parsing it, and a second derivation point is a
        // second answer to "who is this" — with no rule for which answer wins.
        //
        // The header name is matched as a quoted literal, not as bare text: "Authorization" is also
        // the name of a perfectly legitimate namespace in this tree, and a rule that cannot tell a
        // namespace from a header is a rule that gets suppressed rather than obeyed.
        string[] tells =
        [
            "\"Authorization\"",
            "HeaderNames.Authorization",
            "JwtSecurityToken",
            "TokenValidationParameters",
            "ValidateToken",
            "ClaimsPrincipal",
            "AddAuthentication(",
            "AddJwtBearer(",
        ];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(
            offending.Count == 0,
            "Production code reaches for a token. Identity is derived at the Gateway and arrives " +
            "as the closed header contract:\n  " + string.Join("\n  ", offending));
    }

    [Fact]
    public void Only_the_five_gateway_headers_carry_identity()
    {
        // The closed header contract is five names (specification §11.5). Services do not invent
        // alternative identity headers, because a sixth one is a second contract that only one side
        // knows about.
        Assert.Equal(
            ["X-Idp-Client-Surface", "X-Idp-Credential-Class", "X-Idp-Principal-Id", "X-Idp-Roles", "X-Idp-Tenant-Id"],
            typeof(SharedKernel.Identity.IdentityHeaders)
                .GetFields(BindingFlags.Public | BindingFlags.Static)
                .Select(field => (string)field.GetRawConstantValue()!)
                .Order(StringComparer.Ordinal)
                .ToArray());
    }

    [Fact]
    public void No_http_client_is_constructed_by_hand()
    {
        // HttpClient MUST NOT be instantiated manually and one-off unmanaged clients MUST NOT be
        // created (.claude/rules/20-dotnet.md BL-28). Manual instantiation causes socket exhaustion and
        // stale DNS, and it bypasses the resilience handler and timeout every outbound call must
        // carry (research R-020).
        IReadOnlyList<string> offending = SourceTree.ProductionFilesContaining("new HttpClient");

        Assert.True(
            offending.Count == 0,
            "An HttpClient is constructed by hand. Use IHttpClientFactory with a typed client:\n  " +
            string.Join("\n  ", offending));
    }

    [Fact]
    public void No_production_code_uses_a_local_clock()
    {
        // DateTimeOffset throughout, from DateTimeOffset.UtcNow or an injected TimeProvider
        // (.claude/rules/20-dotnet.md DN-1). DateTime.Now silently reads the machine's local zone, which in a
        // container is UTC in production and something else on the developer's laptop.
        string[] tells = ["DateTime.Now", "DateTimeOffset.Now", "DateTime.Today"];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }

    [Fact]
    public void No_production_code_blocks_on_a_task()
    {
        // Never block (.claude/rules/20-dotnet.md BL-23). Blocking a request thread on an async call is how a
        // pool starves under the load it was sized for, and the symptom is latency with no
        // corresponding CPU.
        string[] tells = [".GetAwaiter().GetResult()", ".Wait()", "Task.Run("];

        List<string> offending = [];

        foreach (string tell in tells)
        {
            foreach (string file in SourceTree.ProductionFilesContaining(tell))
            {
                offending.Add($"{file} -> {tell}");
            }
        }

        Assert.True(offending.Count == 0, string.Join("\n  ", offending));
    }

    [Fact]
    public void No_source_file_uses_a_raw_string_literal()
    {
        // Not a style rule. SourceTree.CodeOf strips comments so the guards above can match code
        // rather than prose, and its scanner does not understand """ literals — a raw string
        // containing // would silently truncate the rest of that file from every text-based rule.
        //
        // Either this stays true, or CodeOf learns about raw strings. This test is what forces the
        // choice to be made deliberately.
        List<string> offending = SourceTree.ProductionFiles()
            .Where(file => File.ReadAllText(file.FullName).Contains("\"\"\"", StringComparison.Ordinal))
            .Select(file => file.Name)
            .ToList();

        Assert.True(
            offending.Count == 0,
            "A raw string literal appears in production source. Teach SourceTree.CodeOf about them " +
            "before using one, or the text-based architecture guards stop seeing that file:\n  " +
            string.Join("\n  ", offending));
    }

    [Fact]
    public void Every_async_boundary_takes_a_cancellation_token()
    {
        // CancellationToken propagates through EVERY async boundary (.claude/rules/20-dotnet.md BL-23).
        // Cancellation is honoured before and during blocking I/O so shutdown permits clean
        // Container Apps scale-in, and a read that outlives its caller holds a pooled connection
        // and a request thread for nothing.
        //
        // ONE EXEMPTION, and it is not a loophole: ASP.NET Core fixes the signatures of middleware
        // and endpoint filters, so neither can take a token as a parameter. Both receive one all
        // the same — HttpContext.RequestAborted — so the token is present, just not in the
        // parameter list. The exemption is written as "receives an HttpContext, directly or through
        // a context object that carries one", which is exactly the set of methods that have
        // somewhere else to get it from.
        List<string> offending = [];

        foreach (Assembly assembly in ProductionAssemblies.All)
        {
            foreach (Type type in assembly.GetTypes())
            {
                foreach (MethodInfo method in type.GetMethods(
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly))
                {
                    if (!typeof(Task).IsAssignableFrom(method.ReturnType) &&
                        !typeof(ValueTask).IsAssignableFrom(method.ReturnType) &&
                        !IsGenericTaskLike(method.ReturnType))
                    {
                        continue;
                    }

                    ParameterInfo[] parameters = method.GetParameters();

                    if (parameters.Any(parameter => parameter.ParameterType == typeof(CancellationToken)) ||
                        parameters.Any(parameter => CarriesHttpContext(parameter.ParameterType)))
                    {
                        continue;
                    }

                    offending.Add($"{type.Name}.{method.Name}");
                }
            }
        }

        Assert.True(
            offending.Count == 0,
            "An async boundary takes no CancellationToken and has no HttpContext to read one " +
            "from:\n  " + string.Join("\n  ", offending));
    }

    private static bool CarriesHttpContext(Type parameterType) =>
        parameterType == typeof(HttpContext) ||
        parameterType.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Any(property => property.PropertyType == typeof(HttpContext));

    private static bool IsGenericTaskLike(Type returnType) =>
        returnType.IsGenericType &&
        (returnType.GetGenericTypeDefinition() == typeof(Task<>) ||
         returnType.GetGenericTypeDefinition() == typeof(ValueTask<>));
}
