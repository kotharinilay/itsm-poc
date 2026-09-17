using Synthia.Contracts.Querying;
using Synthia.Modules.Approvals;
using Synthia.Modules.Audit;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;
using Synthia.SharedKernel.Identity;
using Synthia.SharedKernel.Sessions;

namespace Synthia.Api.Querying;

/// <summary>
/// The sortable and filterable field sets, per resource.
/// </summary>
/// <remarks>
/// <para>
/// <b>These are the complete sets from <c>contracts/README.md</c>.</b> A field absent from a set is
/// not sortable or filterable on that resource, and a request naming one is a 400 — never silently
/// ignored. Adding a field is a contract change.
/// </para>
/// <para>
/// Silently ignoring an unknown field is worse than failing on it: the client believes it filtered
/// and receives rows it did not ask for, and on a staff surface those rows can belong to an
/// organisation the caller was not looking at.
/// </para>
/// <para>
/// Each default sort is stated here and matched against the module that knows how to page by it.
/// Two resources cannot satisfy the contract's blanket <c>-createdAt</c> default because
/// <c>createdAt</c> is not in their sortable set; those divergences are recorded on the module
/// constants this file points at, not invented here.
/// </para>
/// </remarks>
internal static class ResourceQueries
{
    /// <summary>
    /// <c>tenantId</c> as a <b>staff-only narrowing</b>, and the single place it is declared.
    /// </summary>
    /// <remarks>
    /// <para>
    /// It selects within the set the caller may already see; it is not a tenant parameter and does
    /// not establish authority (contracts §README rule 1). The value reaches the query as one more
    /// <c>WHERE</c> clause underneath the global scope filter, so a caller naming an organisation
    /// outside their scope receives no rows rather than that organisation's rows.
    /// </para>
    /// <para>
    /// One shared declaration rather than four, because this is the one query field that looks like
    /// authority. <c>build/scripts/openapi_validate.py</c> permits it on the staff documents and on
    /// no other, and fails the build if it appears as anything but a query parameter.
    /// </para>
    /// </remarks>
    private static FilterField TenantNarrowing { get; } =
        new("tenantId", FilterKind.Identifier);

    /// <summary><c>GET /api/customer/v1/views/sessions</c>.</summary>
    public static QueryWhitelist CustomerSessions { get; } = new(
        sortable: ["createdAt", "updatedAt", "state"],
        filterable: [FilterField.Over<SessionState>("state")],
        defaultSort: new SortSpec(SessionSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/customer/v1/views/sessions/{id}/messages</c>.</summary>
    public static QueryWhitelist CustomerSessionMessages { get; } = new(
        sortable: ["createdAt"],
        filterable: [FilterField.Over<SenderKind>("senderKind")],
        defaultSort: new SortSpec("createdAt", SortDirection.Descending));

    /// <summary>
    /// <c>GET /api/customer/v1/views/sessions/{id}/steps</c>.
    /// </summary>
    /// <remarks>
    /// Sortable by <c>createdAt</c> and filterable by nothing. The step trail is a narrative: it
    /// reads oldest-first and is not paged, because a trail with a page boundary in it is not a
    /// trail.
    /// </remarks>
    public static QueryWhitelist CustomerSessionSteps { get; } = new(
        sortable: ["createdAt"],
        filterable: [],
        defaultSort: new SortSpec("createdAt", SortDirection.Ascending));

    /// <summary><c>GET /api/customer/v1/views/sessions/{sessionId}/feedback</c>.</summary>
    /// <remarks>
    /// Nothing filterable. A filter on <c>signal</c> would let a caller ask which of their messages
    /// they rated down, which is a question the read path has no reason to answer — and the set is
    /// one session's worth of rows, so there is nothing to page through either.
    /// </remarks>
    public static QueryWhitelist CustomerSessionFeedback { get; } = new(
        sortable: ["updatedAt"],
        filterable: [],
        defaultSort: new SortSpec("updatedAt", SortDirection.Ascending));

    /// <summary><c>GET /api/staff/v1/views/sessions/live</c>.</summary>
    public static QueryWhitelist StaffLiveSessions { get; } = new(
        sortable: ["createdAt", "updatedAt", "state"],
        filterable: [FilterField.Over<SessionState>("state"), TenantNarrowing],
        defaultSort: new SortSpec(SessionSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/approvals/queue</c>.</summary>
    public static QueryWhitelist StaffApprovalQueue { get; } = new(
        sortable: ["createdAt", "expiresAt"],
        filterable: [TenantNarrowing],
        defaultSort: new SortSpec(ApprovalSortKeys.QueueDefault, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/approvals/unexecuted</c>.</summary>
    public static QueryWhitelist StaffUnexecutedApprovals { get; } = new(
        sortable: ["decidedAt", "expiresAt"],
        filterable: [TenantNarrowing],
        defaultSort: new SortSpec(ApprovalSortKeys.UnexecutedDefault, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/audit</c>.</summary>
    public static QueryWhitelist StaffAudit { get; } = new(
        sortable: ["occurredAt"],
        filterable:
        [
            TenantNarrowing,
            new FilterField("workItemId", FilterKind.Identifier),
            new FilterField("eventKind", FilterKind.Text),
            new FilterField("occurredFrom", FilterKind.Timestamp),
            new FilterField("occurredTo", FilterKind.Timestamp),
        ],
        defaultSort: new SortSpec(AuditSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/tenants</c>.</summary>
    public static QueryWhitelist StaffTenants { get; } = new(
        sortable: ["displayName", "status"],
        filterable: [FilterField.Over<TenantStatus>("status")],
        defaultSort: new SortSpec(TenantSortKeys.Default, SortDirection.Ascending));
}
