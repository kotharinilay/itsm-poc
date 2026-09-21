namespace Synthia.Contracts.Boundaries;

/// <summary>Which deployable owns the behaviour behind a platform boundary.</summary>
public enum BoundaryOwner
{
    /// <summary>Unset. Never valid on a declared boundary.</summary>
    Unknown = 0,

    /// <summary>This deployable — the read-only .NET modular monolith.</summary>
    Monolith = 1,

    /// <summary>The RagCore deployable, which owns orchestration, execution and every write.</summary>
    RagCore = 2,

    /// <summary>Platform infrastructure outside either application (gateway, registry, vault).</summary>
    Platform = 3,
}

/// <summary>How this deployable relates to a boundary it does not own.</summary>
public enum MonolithRelationship
{
    /// <summary>Unset.</summary>
    Unknown = 0,

    /// <summary>The monolith implements the behaviour itself.</summary>
    Owns = 1,

    /// <summary>The monolith reads the result through a published view. No client, no coupling.</summary>
    ReadsThroughPublishedView = 2,

    /// <summary>The monolith consumes it as ambient infrastructure, not as an application dependency.</summary>
    ConsumesAsInfrastructure = 3,

    /// <summary>
    /// The monolith has no relationship at all: no client library, no type, no configuration.
    /// </summary>
    None = 4,
}

/// <summary>
/// One named boundary, and this deployable's declared relationship to it.
/// </summary>
/// <param name="Name">The boundary, in the vocabulary A2 §5 uses.</param>
/// <param name="Owner">Which deployable owns the behaviour.</param>
/// <param name="Relationship">What, if anything, the monolith does about it.</param>
/// <param name="Rationale">Why the relationship is what it is, citing the governing document.</param>
public sealed record PlatformBoundary(
    string Name,
    BoundaryOwner Owner,
    MonolithRelationship Relationship,
    string Rationale);

/// <summary>
/// The boundaries this platform has, and which side of each one the monolith sits on.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is a boundary register, not a set of ports.</b> A port would be a speculative
/// abstraction: a provider-neutral interface MUST NOT be created until a real second provider
/// exists (.claude/rules/10-principles.md P-8), and for every entry below marked
/// <see cref="MonolithRelationship.None"/> there is no first provider in this deployable either —
/// the behaviour lives in RagCore, which is written in Python and can never implement a .NET
/// interface.
/// </para>
/// <para>
/// Writing the boundary down and testing it is what makes it real. <c>BoundaryOwnershipTests</c>
/// asserts that every <see cref="MonolithRelationship.None"/> entry stays that way: no client
/// package, no type, no configuration section creeps in. That is a stronger guarantee than an
/// interface nobody implements, and an honest one — it says the boundary exists and states which
/// side of it we are on, rather than pretending to straddle it.
/// </para>
/// </remarks>
public static class PlatformBoundaries
{
    /// <summary>Azure Service Bus — the verdict-to-execution seam.</summary>
    public const string ServiceBus = "azure-service-bus";

    /// <summary>The transactional outbox that makes a state change and its message equally durable.</summary>
    public const string TransactionalOutbox = "transactional-outbox";

    /// <summary>Idempotency-key handling and replay for state-changing operations.</summary>
    public const string Idempotency = "idempotency";

    /// <summary>Key Vault — the sole source of secret material.</summary>
    public const string KeyVault = "key-vault";

    /// <summary>The PostgreSQL published-view contract between the two deployables.</summary>
    public const string PublishedViews = "published-views";

    /// <summary>Model egress, which routes exclusively through the AI Gateway.</summary>
    public const string ModelEgress = "model-egress";

    /// <summary>The system of record.</summary>
    public const string ServiceNow = "integration-servicenow";

    /// <summary>Microsoft Graph.</summary>
    public const string MicrosoftGraph = "integration-microsoft-graph";

    /// <summary>Realtime notification delivery.</summary>
    public const string Realtime = "realtime-signalr";

    /// <summary>Azure Container Apps — the runtime this deployable is configured for.</summary>
    public const string ContainerAppsRuntime = "container-apps-runtime";

    private static readonly PlatformBoundary[] _all =
    [
        new(
            ServiceBus,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "The monolith is read-only and publishes nothing (ADR-0001). Both the publisher and " +
            "the resume consumer are RagCore workers. A trigger carries only workItemId, " +
            "correlationId and kind, and is untrusted (contracts/triggers.md)."),
        new(
            TransactionalOutbox,
            BoundaryOwner.RagCore,
            MonolithRelationship.ReadsThroughPublishedView,
            "The outbox row commits in the same transaction as the state change it describes " +
            "(research R-017). Only a writer needs an outbox, and the monolith never writes. Its " +
            "one interest is the undispatchable case, which surfaces through " +
            "vw_approval_unexecuted_v1 (ADR-0002)."),
        new(
            Idempotency,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "Any state-changing endpoint accepts Idempotency-Key (contracts/README.md). The " +
            "monolith exposes no state-changing endpoint, so it has no key to honour and no " +
            "outcome to replay. Idempotency state is persisted in PostgreSQL by RagCore."),
        new(
            KeyVault,
            BoundaryOwner.Platform,
            MonolithRelationship.ConsumesAsInfrastructure,
            "Key Vault is the sole source of secret material (A2 P09). The " +
            "monolith resolves secrets through managed identity as a configuration source, which " +
            "is infrastructure, not an application dependency."),
        new(
            PublishedViews,
            BoundaryOwner.RagCore,
            MonolithRelationship.ReadsThroughPublishedView,
            "RagCore owns every table, every view and every migration. The monolith holds SELECT " +
            "on published views only: no table access, no DDL, no migrations (contracts/read-views.md)."),
        new(
            ModelEgress,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "Model access routes exclusively through the AI Gateway from RagCore. No module holds " +
            "a provider endpoint (A2 §9)."),
        new(
            ServiceNow,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "The sole path to the system of record is the RagCore adapter. The monolith holds no " +
            "adapter and no case-management behaviour; it reads a case reference as an opaque string."),
        new(
            MicrosoftGraph,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "Behind its port in RagCore. The monolith never calls Graph — identity is derived once " +
            "at the Gateway and arrives as headers (A1 §4.5)."),
        new(
            Realtime,
            BoundaryOwner.RagCore,
            MonolithRelationship.None,
            "SignalR delivers notification and results only, published by RagCore through the " +
            "data-plane REST API. The monolith neither publishes nor negotiates."),
        new(
            ContainerAppsRuntime,
            BoundaryOwner.Platform,
            MonolithRelationship.ConsumesAsInfrastructure,
            "HTTP health probes, explicit resource limits and a 25-second drain are runtime " +
            "configuration (plan Stage 10). The application exposes the probes; the platform " +
            "decides when to call them."),
    ];

    /// <summary>Every declared boundary.</summary>
    public static IReadOnlyList<PlatformBoundary> All => _all;

    /// <summary>
    /// The boundaries this deployable must carry no trace of.
    /// </summary>
    /// <remarks>
    /// Each of these is asserted absent by an architecture test. An entry moving off this list is a
    /// recorded architectural decision, not a refactor.
    /// </remarks>
    public static IEnumerable<PlatformBoundary> NotPresentInThisDeployable =>
        _all.Where(boundary => boundary.Relationship == MonolithRelationship.None);
}
