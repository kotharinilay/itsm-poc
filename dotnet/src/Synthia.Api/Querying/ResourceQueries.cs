using Synthia.Contracts.Querying;
using Synthia.Modules.Approvals;
using Synthia.Modules.Audit;
using Synthia.Modules.Sessions;
using Synthia.Modules.Tenancy;

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
    /// <summary><c>GET /api/customer/v1/views/sessions</c>.</summary>
    public static QueryWhitelist CustomerSessions { get; } = new(
        sortable: ["createdAt", "updatedAt", "state"],
        filterable: ["state"],
        defaultSort: new SortSpec(SessionSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/customer/v1/views/sessions/{id}/messages</c>.</summary>
    public static QueryWhitelist CustomerSessionMessages { get; } = new(
        sortable: ["createdAt"],
        filterable: ["senderKind"],
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

    /// <summary><c>GET /api/staff/v1/views/sessions/live</c>.</summary>
    public static QueryWhitelist StaffLiveSessions { get; } = new(
        sortable: ["createdAt", "updatedAt", "state"],
        filterable: ["state", "tenantId"],
        defaultSort: new SortSpec(SessionSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/approvals/queue</c>.</summary>
    public static QueryWhitelist StaffApprovalQueue { get; } = new(
        sortable: ["createdAt", "expiresAt"],
        filterable: ["tenantId"],
        defaultSort: new SortSpec(ApprovalSortKeys.QueueDefault, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/approvals/unexecuted</c>.</summary>
    public static QueryWhitelist StaffUnexecutedApprovals { get; } = new(
        sortable: ["decidedAt", "expiresAt"],
        filterable: ["tenantId"],
        defaultSort: new SortSpec(ApprovalSortKeys.UnexecutedDefault, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/audit</c>.</summary>
    public static QueryWhitelist StaffAudit { get; } = new(
        sortable: ["occurredAt"],
        filterable: ["tenantId", "workItemId", "eventKind", "occurredFrom", "occurredTo"],
        defaultSort: new SortSpec(AuditSortKeys.Default, SortDirection.Descending));

    /// <summary><c>GET /api/staff/v1/views/tenants</c>.</summary>
    public static QueryWhitelist StaffTenants { get; } = new(
        sortable: ["displayName", "status"],
        filterable: ["status"],
        defaultSort: new SortSpec(TenantSortKeys.Default, SortDirection.Ascending));
}
