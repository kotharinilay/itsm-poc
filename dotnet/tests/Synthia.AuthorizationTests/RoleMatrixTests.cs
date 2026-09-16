using Synthia.SharedKernel.Authorization;
using Synthia.SharedKernel.Identity;

namespace Synthia.AuthorizationTests;

/// <summary>
/// The full authorization matrix: every role combination against every operation (T158).
/// </summary>
/// <remarks>
/// <para>
/// <b>Exhaustive, not representative.</b> Every subset of the role set is tried against every
/// operation, including the empty one. Authorization is set intersection, and the failure mode of a
/// set-intersection bug is a combination nobody thought to try — so the test tries all of them
/// rather than the ones that came to mind (spec SC-AUTHZ-001).
/// </para>
/// <para>
/// The operations are the read routes this deployable actually exposes, with the accepted set each
/// one declares. When a route is added without a row here, <c>Every_operation_is_covered</c> fails.
/// </para>
/// </remarks>
public sealed class RoleMatrixTests
{
    private static readonly StaffRole[] _allRoles =
    [
        StaffRole.EndUser,
        StaffRole.Technician,
        StaffRole.SeniorTechnician,
        StaffRole.Administrator,
    ];

    /// <summary>
    /// The operations this deployable exposes and the roles each accepts.
    /// </summary>
    /// <remarks>
    /// Transcribed from <c>contracts/staff-api.md</c> and <c>contracts/customer-api.md</c> rather
    /// than read from the application. A matrix test that asked the application what it accepts
    /// would agree with the application however wrong it was.
    /// </remarks>
    public static TheoryData<string, StaffRole[]> Operations() => new()
    {
        { "GET /api/customer/v1/views/sessions", [StaffRole.EndUser] },
        { "GET /api/customer/v1/views/sessions/{id}", [StaffRole.EndUser] },
        { "GET /api/customer/v1/views/sessions/{id}/messages", [StaffRole.EndUser] },
        { "GET /api/customer/v1/views/sessions/{id}/steps", [StaffRole.EndUser] },
        { "GET /api/staff/v1/views/sessions/live", [StaffRole.Technician] },
        { "GET /api/staff/v1/views/sessions/{id}", [StaffRole.Technician] },
        { "GET /api/staff/v1/views/approvals/queue", [StaffRole.Technician] },
        { "GET /api/staff/v1/views/approvals/unexecuted", [StaffRole.Technician] },
        { "GET /api/staff/v1/views/audit", [StaffRole.Technician] },
        { "GET /api/staff/v1/views/dashboard/platform", [StaffRole.Administrator] },
        { "GET /api/staff/v1/views/tenants", [StaffRole.Administrator] },
    };

    [Theory]
    [MemberData(nameof(Operations))]
    public void Every_role_combination_is_decided_by_intersection(string operation, StaffRole[] accepted)
    {
        ArgumentNullException.ThrowIfNull(accepted);

        RoleSet acceptedSet = RoleSet.Of(accepted);
        List<string> wrong = [];

        foreach (StaffRole[] held in AllSubsets(_allRoles))
        {
            RoleSet heldSet = RoleSet.Of(held);

            AuthorizationDecision decision = RoleIntersection.Evaluate(heldSet, acceptedSet);

            bool intersects = held.Any(role => accepted.Contains(role));

            if (decision.IsPermitted != intersects)
            {
                wrong.Add($"{operation}: held {{{string.Join(", ", held)}}} -> {decision.IsPermitted}");
            }
        }

        Assert.True(wrong.Count == 0, string.Join("\n  ", wrong));
    }

    [Fact]
    public void The_empty_intersection_denies_every_operation()
    {
        // An empty intersection denies, and an operation that accepts no roles denies everyone
        // (constitution Principle II). Both halves matter: the first is the common case, the second
        // is what stops a misconfigured operation defaulting open.
        foreach (object[] row in Operations().Select(r => r.ToArray()))
        {
            RoleSet accepted = RoleSet.Of((StaffRole[])row[1]);

            Assert.False(RoleIntersection.Evaluate(RoleSet.Empty, accepted).IsPermitted);
            Assert.False(RoleIntersection.Evaluate(accepted, RoleSet.Empty).IsPermitted);
        }
    }

    [Fact]
    public void No_operation_accepts_senior_technician()
    {
        // senior_technician exists as a defined role that no operation accepts until one is
        // explicitly introduced (constitution Principle II). Asserted so introducing one is a
        // deliberate change to this file rather than a side effect of a copied route.
        foreach (object[] row in Operations().Select(r => r.ToArray()))
        {
            Assert.DoesNotContain(StaffRole.SeniorTechnician, (StaffRole[])row[1]);
        }
    }

    [Fact]
    public void Holding_several_roles_grants_the_union_and_nothing_further()
    {
        // A principal holding several roles receives the union of those capabilities and nothing
        // further (constitution Principle II). The "nothing further" half is the one that matters:
        // {technician, administrator} must not unlock an operation neither accepts alone.
        RoleSet both = RoleSet.Of(StaffRole.Technician, StaffRole.Administrator);

        Assert.True(RoleIntersection.Evaluate(both, RoleSet.Of(StaffRole.Technician)).IsPermitted);
        Assert.True(RoleIntersection.Evaluate(both, RoleSet.Of(StaffRole.Administrator)).IsPermitted);
        Assert.False(RoleIntersection.Evaluate(both, RoleSet.Of(StaffRole.SeniorTechnician)).IsPermitted);
        Assert.False(RoleIntersection.Evaluate(both, RoleSet.Empty).IsPermitted);
    }

    private static IEnumerable<StaffRole[]> AllSubsets(StaffRole[] roles)
    {
        for (int mask = 0; mask < 1 << roles.Length; mask++)
        {
            List<StaffRole> subset = [];

            for (int index = 0; index < roles.Length; index++)
            {
                if ((mask & (1 << index)) != 0)
                {
                    subset.Add(roles[index]);
                }
            }

            yield return [.. subset];
        }
    }
}
