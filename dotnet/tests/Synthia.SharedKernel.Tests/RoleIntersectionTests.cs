using Synthia.SharedKernel.Authorization;

namespace Synthia.SharedKernel.Tests;

/// <summary>
/// Set-intersection authorization (T031).
/// </summary>
/// <remarks>
/// Mirrors <c>ragcore/tests/unit/test_roles.py</c>. The two stacks are proven <b>independently</b>
/// rather than sharing a fixture: they share no code, and a bug in one must not be masked by the
/// other passing.
/// </remarks>
public sealed class RoleIntersectionTests
{
    [Fact]
    public void Administrator_does_not_imply_technician()
    {
        RoleSet administrator = RoleSet.Of(StaffRole.Administrator);

        Assert.False(administrator.Contains(StaffRole.Technician));
        Assert.False(RoleIntersection.Evaluate(administrator, StaffRole.Technician).IsPermitted);
    }

    [Fact]
    public void Technician_does_not_imply_administrator()
    {
        RoleSet technician = RoleSet.Of(StaffRole.Technician);

        Assert.False(RoleIntersection.Evaluate(technician, StaffRole.Administrator).IsPermitted);
    }

    [Fact]
    public void Staff_role_defines_no_ordering()
    {
        // The compile-time guarantee is the real one: StaffRole is a record struct with equality
        // and nothing else, so `role1 < role2` does not compile. This asserts the runtime half —
        // that nobody reintroduced IComparable to make some sort call convenient.
        Assert.False(typeof(StaffRole).IsAssignableTo(typeof(IComparable)));
        Assert.False(typeof(StaffRole).IsAssignableTo(typeof(IComparable<StaffRole>)));
        Assert.False(typeof(RoleSet).IsAssignableTo(typeof(IComparable)));
    }

    [Fact]
    public void Staff_role_is_not_an_enum()
    {
        // An enum is integer-backed and therefore ordered for free — exactly the ranking the
        // constitution prohibits. If someone "simplifies" this type to an enum, this fails.
        Assert.False(typeof(StaffRole).IsEnum);
    }

    [Fact]
    public void Overlapping_sets_permit()
    {
        AuthorizationDecision decision =
            RoleIntersection.Evaluate(RoleSet.Of(StaffRole.Technician), StaffRole.Technician);

        Assert.True(decision.IsPermitted);
        Assert.Equal(DenialReason.None, decision.Reason);
    }

    [Fact]
    public void Disjoint_sets_deny_on_empty_intersection()
    {
        AuthorizationDecision decision =
            RoleIntersection.Evaluate(RoleSet.Of(StaffRole.Administrator), StaffRole.Technician);

        Assert.False(decision.IsPermitted);
        Assert.Equal(DenialReason.EmptyIntersection, decision.Reason);
    }

    [Fact]
    public void Multiple_roles_receive_the_union_and_nothing_further()
    {
        RoleSet both = RoleSet.Of(StaffRole.Technician, StaffRole.Administrator);

        Assert.True(RoleIntersection.Evaluate(both, StaffRole.Technician).IsPermitted);
        Assert.True(RoleIntersection.Evaluate(both, StaffRole.Administrator).IsPermitted);

        // Nothing further: senior_technician was not granted by holding the other two.
        Assert.False(RoleIntersection.Evaluate(both, StaffRole.SeniorTechnician).IsPermitted);
    }

    [Fact]
    public void One_shared_role_is_enough()
    {
        RoleSet held = RoleSet.Of(StaffRole.Administrator, StaffRole.Technician);
        RoleSet accepted = RoleSet.Of(StaffRole.Technician, StaffRole.SeniorTechnician);

        Assert.True(RoleIntersection.Evaluate(held, accepted).IsPermitted);
    }

    [Theory]
    [MemberData(nameof(EveryRoleCombination))]
    public void Operation_accepting_no_roles_denies_everyone(RoleSet held)
    {
        // An empty accepted set is a TOTAL denial, never an implicit allow (spec FR-AUTHZ-010).
        AuthorizationDecision decision = RoleIntersection.Evaluate(held, RoleSet.Empty);

        Assert.False(decision.IsPermitted);
        Assert.Equal(DenialReason.OperationAcceptsNoRoles, decision.Reason);
    }

    [Fact]
    public void Principal_holding_no_roles_is_denied()
    {
        AuthorizationDecision decision =
            RoleIntersection.Evaluate(RoleSet.Empty, StaffRole.Technician);

        Assert.False(decision.IsPermitted);
        Assert.Equal(DenialReason.PrincipalHoldsNoRoles, decision.Reason);
    }

    [Fact]
    public void Decision_records_the_role_set_held_at_decision_time()
    {
        RoleSet held = RoleSet.Of(StaffRole.Administrator);

        // Recorded on refusals too: a denial is audited as durably as a permission.
        AuthorizationDecision denied = RoleIntersection.Evaluate(held, StaffRole.Technician);
        Assert.Equal(held, denied.RolesHeldAtDecision);

        AuthorizationDecision permitted = RoleIntersection.Evaluate(held, StaffRole.Administrator);
        Assert.Equal(held, permitted.RolesHeldAtDecision);
    }

    [Fact]
    public void Technician_may_approve_and_administrator_may_not()
    {
        // The initial-release assignment, asserted rather than assumed.
        RoleSet approvalAccepts = RoleSet.Of(StaffRole.Technician);

        Assert.True(RoleIntersection.Evaluate(RoleSet.Of(StaffRole.Technician), approvalAccepts).IsPermitted);
        Assert.False(RoleIntersection.Evaluate(RoleSet.Of(StaffRole.Administrator), approvalAccepts).IsPermitted);
    }

    [Fact]
    public void Senior_technician_is_accepted_by_no_operation()
    {
        RoleSet held = RoleSet.Of(StaffRole.SeniorTechnician);

        Assert.False(RoleIntersection.Evaluate(held, StaffRole.Technician).IsPermitted);
        Assert.False(RoleIntersection.Evaluate(held, StaffRole.Administrator).IsPermitted);
        Assert.False(RoleIntersection.Evaluate(held, StaffRole.EndUser).IsPermitted);
    }

    [Theory]
    [InlineData("technician")]
    [InlineData("senior_technician")]
    [InlineData("administrator")]
    [InlineData("end_user")]
    [InlineData("none")]
    public void Canonical_names_parse(string name)
    {
        Assert.True(StaffRole.TryParse(name, out StaffRole role));
        Assert.Equal(name, role.Name);
    }

    [Theory]
    [InlineData("Technician")]
    [InlineData("TECHNICIAN")]
    [InlineData(" technician")]
    [InlineData("technician ")]
    [InlineData("tech")]
    [InlineData("")]
    [InlineData(null)]
    public void Non_canonical_spellings_are_refused(string? candidate)
    {
        // Refused rather than repaired: repairing widens the set of accepted spellings beyond the
        // set that was reviewed.
        Assert.False(StaffRole.TryParse(candidate, out _));
    }

    [Fact]
    public void Role_set_equality_ignores_order()
    {
        Assert.Equal(
            RoleSet.Of(StaffRole.Technician, StaffRole.Administrator),
            RoleSet.Of(StaffRole.Administrator, StaffRole.Technician));
    }

    [Fact]
    public void Role_set_renders_in_ascending_ordinal_order()
    {
        Assert.Equal(
            "administrator,technician",
            RoleSet.Of(StaffRole.Technician, StaffRole.Administrator).ToString());
    }

    public static TheoryData<RoleSet> EveryRoleCombination()
    {
        StaffRole[] all =
        [
            StaffRole.EndUser,
            StaffRole.Technician,
            StaffRole.SeniorTechnician,
            StaffRole.Administrator,
        ];

        TheoryData<RoleSet> data = [];

        // Every subset, including the empty one.
        for (int mask = 0; mask < 1 << all.Length; mask++)
        {
            List<StaffRole> subset = [];
            for (int bit = 0; bit < all.Length; bit++)
            {
                if ((mask & (1 << bit)) != 0)
                {
                    subset.Add(all[bit]);
                }
            }

            data.Add(RoleSet.From(subset));
        }

        return data;
    }
}
