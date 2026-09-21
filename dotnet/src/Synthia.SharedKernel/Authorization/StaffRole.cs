using System.Collections.Frozen;
using System.Globalization;

namespace Synthia.SharedKernel.Authorization;

/// <summary>
/// A staff capability. Roles are <b>disjoint capability sets, never a hierarchy</b>.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is deliberately not an enum.</b> A C# enum is backed by an integer and therefore carries
/// <c>&lt;</c>, <c>&gt;</c> and <see cref="IComparable"/> for free — which is exactly the ordering
/// A1 §6 prohibits. Making the type a record struct with equality and
/// nothing else means "is this role greater than that one" does not compile, rather than compiling
/// and being caught in review, or not being caught at all.
/// </para>
/// <para>
/// <c>administrator</c> does NOT imply <c>technician</c>. Any implementation that sorts, ranks,
/// compares or upgrades roles is a defect.
/// </para>
/// </remarks>
public readonly record struct StaffRole
{
    private readonly string? _name;

    private StaffRole(string name) => _name = name;

    /// <summary>The canonical role name. Empty for a default-constructed value.</summary>
    public string Name => _name ?? string.Empty;

    /// <summary>Any person acting on a customer surface, including staff doing so.</summary>
    public static StaffRole EndUser { get; } = new("end_user");

    /// <summary>The role that may approve in the initial release.</summary>
    public static StaffRole Technician { get; } = new("technician");

    /// <summary>
    /// A defined role that no operation accepts in the initial release (spec FR-AUTHZ-008).
    /// Its presence is what keeps the no-hierarchy rule honest: a set with a member that grants
    /// nothing cannot be quietly reimplemented as a rank.
    /// </summary>
    public static StaffRole SeniorTechnician { get; } = new("senior_technician");

    /// <summary>Platform administration. Does NOT imply <see cref="Technician"/>.</summary>
    public static StaffRole Administrator { get; } = new("administrator");

    /// <summary>The sentinel carried by an app-only (Workload) credential.</summary>
    public static StaffRole None { get; } = new("none");

    private static readonly FrozenDictionary<string, StaffRole> _byName =
        new Dictionary<string, StaffRole>(StringComparer.Ordinal)
        {
            [EndUser.Name] = EndUser,
            [Technician.Name] = Technician,
            [SeniorTechnician.Name] = SeniorTechnician,
            [Administrator.Name] = Administrator,
            [None.Name] = None,
        }.ToFrozenDictionary(StringComparer.Ordinal);

    /// <summary>
    /// Parses a canonical role name from the Gateway-derived header contract.
    /// </summary>
    /// <remarks>
    /// Matching is <b>ordinal and case-sensitive</b>. The specification makes the canonical form a
    /// security property rather than tidiness: accepting <c>Administrator</c> or
    /// <c>ADMINISTRATOR</c> would mean the set of accepted spellings is larger than the set that
    /// was reviewed.
    /// </remarks>
    /// <param name="name">The candidate role name.</param>
    /// <param name="role">The parsed role, when recognised.</param>
    /// <returns><see langword="true"/> when the name is a canonical role.</returns>
    public static bool TryParse(string? name, out StaffRole role)
    {
        if (name is not null && _byName.TryGetValue(name, out StaffRole found))
        {
            role = found;
            return true;
        }

        role = default;
        return false;
    }

    /// <summary>Renders the canonical role name.</summary>
    /// <returns>The role name.</returns>
    public override string ToString() => Name;
}

/// <summary>
/// The set of roles a principal holds, or the set an operation accepts.
/// </summary>
/// <remarks>
/// A set, not a list: order carries no meaning and duplicates say nothing. The type exposes
/// <see cref="Intersects"/> and nothing that could be mistaken for a ranking.
/// </remarks>
public readonly struct RoleSet : IEquatable<RoleSet>
{
    private readonly FrozenSet<StaffRole>? _roles;

    private RoleSet(FrozenSet<StaffRole> roles) => _roles = roles;

    /// <summary>The empty set. An operation accepting it denies everyone.</summary>
    public static RoleSet Empty { get; } = new(FrozenSet<StaffRole>.Empty);

    /// <summary>The roles in this set.</summary>
    public IReadOnlyCollection<StaffRole> Roles => _roles ?? FrozenSet<StaffRole>.Empty;

    /// <summary>The number of distinct roles held.</summary>
    public int Count => Roles.Count;

    /// <summary>Whether the set holds no roles.</summary>
    public bool IsEmpty => Count == 0;

    /// <summary>Creates a set from the given roles, discarding duplicates.</summary>
    /// <param name="roles">The roles to include.</param>
    /// <returns>The resulting set.</returns>
    public static RoleSet Of(params StaffRole[] roles) =>
        roles is null or { Length: 0 } ? Empty : new RoleSet(roles.ToFrozenSet());

    /// <summary>Creates a set from a sequence of roles.</summary>
    /// <param name="roles">The roles to include.</param>
    /// <returns>The resulting set.</returns>
    public static RoleSet From(IEnumerable<StaffRole> roles) =>
        roles is null ? Empty : new RoleSet(roles.ToFrozenSet());

    /// <summary>Whether this set shares at least one role with <paramref name="other"/>.</summary>
    /// <param name="other">The set to intersect with.</param>
    /// <returns><see langword="true"/> when the intersection is non-empty.</returns>
    public bool Intersects(RoleSet other)
    {
        foreach (StaffRole role in Roles)
        {
            if (other.Contains(role))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>Whether this set holds the given role.</summary>
    /// <param name="role">The role to look for.</param>
    /// <returns><see langword="true"/> when present.</returns>
    public bool Contains(StaffRole role) => _roles?.Contains(role) ?? false;

    /// <inheritdoc />
    public bool Equals(RoleSet other) => Count == other.Count && AllPresentIn(other);

    private bool AllPresentIn(RoleSet other)
    {
        foreach (StaffRole role in Roles)
        {
            if (!other.Contains(role))
            {
                return false;
            }
        }

        return true;
    }

    /// <inheritdoc />
    public override bool Equals(object? obj) => obj is RoleSet other && Equals(other);

    /// <inheritdoc />
    public override int GetHashCode()
    {
        int hash = 0;
        foreach (StaffRole role in Roles)
        {
            // XOR: order-independent, which is the point of a set.
            hash ^= role.GetHashCode();
        }

        return hash;
    }

    /// <summary>Equality operator.</summary>
    /// <param name="left">Left operand.</param>
    /// <param name="right">Right operand.</param>
    /// <returns><see langword="true"/> when the sets hold the same roles.</returns>
    public static bool operator ==(RoleSet left, RoleSet right) => left.Equals(right);

    /// <summary>Inequality operator.</summary>
    /// <param name="left">Left operand.</param>
    /// <param name="right">Right operand.</param>
    /// <returns><see langword="true"/> when the sets differ.</returns>
    public static bool operator !=(RoleSet left, RoleSet right) => !left.Equals(right);

    /// <summary>Renders the set in canonical order, for logging only.</summary>
    /// <returns>A comma-separated role list.</returns>
    public override string ToString() =>
        string.Join(',', Roles.Select(r => r.Name).Order(StringComparer.Ordinal));
}
