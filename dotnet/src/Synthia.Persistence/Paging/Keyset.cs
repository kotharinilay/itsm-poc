using System.Globalization;
using System.Linq.Expressions;
using System.Reflection;
using Microsoft.EntityFrameworkCore;

namespace Synthia.Persistence.Paging;

/// <summary>Which way a keyset scan runs.</summary>
/// <remarks>
/// Deliberately not <c>Synthia.Contracts.Querying.SortDirection</c>: persistence sits below
/// contracts in the dependency graph and may not reference it (plan §Dependency direction). The two
/// enums say the same thing on opposite sides of a boundary, and a module translates between them.
/// </remarks>
public enum KeysetDirection
{
    /// <summary>Ascending.</summary>
    Ascending = 0,

    /// <summary>Descending — the default for every timestamp sort in the contracts.</summary>
    Descending = 1,
}

/// <summary>
/// Where a scan resumes: the last row's sort value, rendered, plus its identifier.
/// </summary>
/// <param name="SortValue">The last row's sort key, rendered round-trippably.</param>
/// <param name="Id">The last row's identifier, breaking ties on equal sort values.</param>
public readonly record struct KeysetAnchor(string SortValue, Guid Id);

/// <summary>One page of rows, plus where the next page resumes.</summary>
/// <typeparam name="TRow">The view row type.</typeparam>
/// <param name="Rows">The rows in this page.</param>
/// <param name="Next">Where to resume, or <see langword="null"/> when the scan is exhausted.</param>
public sealed record KeysetSlice<TRow>(IReadOnlyList<TRow> Rows, KeysetAnchor? Next);

/// <summary>
/// One whitelisted sort field, and everything needed to page by it.
/// </summary>
/// <remarks>
/// A sort field is not just a column name: paging by it needs an ordering, a strict comparison
/// against the anchor, and a way to render the value into a cursor and read it back. Bundling the
/// four means a resource declares a sortable field once and cannot declare half of it.
/// </remarks>
/// <typeparam name="TRow">The view row type.</typeparam>
public interface IKeysetSortKey<TRow>
    where TRow : class
{
    /// <summary>The field name as the contract spells it, in camelCase.</summary>
    string Field { get; }

    /// <summary>Orders a query by this field, with the identifier as the tie-break.</summary>
    /// <param name="source">The query to order.</param>
    /// <param name="direction">Which way.</param>
    /// <returns>The ordered query.</returns>
    IQueryable<TRow> Order(IQueryable<TRow> source, KeysetDirection direction);

    /// <summary>
    /// Restricts a query to rows strictly after the anchor in the given direction.
    /// </summary>
    /// <param name="source">The query to restrict.</param>
    /// <param name="direction">Which way the scan runs.</param>
    /// <param name="anchor">Where the previous page ended.</param>
    /// <returns>The restricted query.</returns>
    /// <exception cref="FormatException">The cursor did not carry a value this field can read.</exception>
    IQueryable<TRow> After(IQueryable<TRow> source, KeysetDirection direction, KeysetAnchor anchor);

    /// <summary>Renders a row into the anchor a client would resume from.</summary>
    /// <param name="row">The last row of a page.</param>
    /// <returns>The anchor.</returns>
    KeysetAnchor AnchorOf(TRow row);
}

/// <summary>
/// A whitelisted sort field of a known type.
/// </summary>
/// <typeparam name="TRow">The view row type.</typeparam>
/// <typeparam name="TKey">The CLR type of the sort column.</typeparam>
public sealed class KeysetSortKey<TRow, TKey> : IKeysetSortKey<TRow>
    where TRow : class
{
    private readonly Expression<Func<TRow, TKey>> _selector;
    private readonly Expression<Func<TRow, Guid>> _identity;
    private readonly Func<TRow, TKey> _readKey;
    private readonly Func<TRow, Guid> _readId;
    private readonly Func<TKey, string> _render;
    private readonly Func<string, TKey> _parse;

    /// <summary>Declares a sortable field.</summary>
    /// <param name="field">The field name as the contract spells it.</param>
    /// <param name="selector">Reads the sort column from a row.</param>
    /// <param name="identity">Reads the row identifier, which breaks ties.</param>
    /// <param name="render">Renders a sort value into a cursor.</param>
    /// <param name="parse">Reads a sort value back out of a cursor.</param>
    public KeysetSortKey(
        string field,
        Expression<Func<TRow, TKey>> selector,
        Expression<Func<TRow, Guid>> identity,
        Func<TKey, string> render,
        Func<string, TKey> parse)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(field);
        ArgumentNullException.ThrowIfNull(selector);
        ArgumentNullException.ThrowIfNull(identity);
        ArgumentNullException.ThrowIfNull(render);
        ArgumentNullException.ThrowIfNull(parse);

        Field = field;
        _selector = selector;
        _identity = identity;
        _readKey = selector.Compile();
        _readId = identity.Compile();
        _render = render;
        _parse = parse;
    }

    /// <inheritdoc/>
    public string Field { get; }

    /// <inheritdoc/>
    public IQueryable<TRow> Order(IQueryable<TRow> source, KeysetDirection direction)
    {
        ArgumentNullException.ThrowIfNull(source);

        return direction == KeysetDirection.Ascending
            ? source.OrderBy(_selector).ThenBy(_identity)
            : source.OrderByDescending(_selector).ThenByDescending(_identity);
    }

    /// <inheritdoc/>
    public IQueryable<TRow> After(IQueryable<TRow> source, KeysetDirection direction, KeysetAnchor anchor)
    {
        ArgumentNullException.ThrowIfNull(source);

        TKey lastKey = _parse(anchor.SortValue);

        // (key, id) > (lastKey, lastId) — as one predicate, not two passes. The identifier is what
        // makes a page boundary inside a run of equal timestamps neither repeat a row nor skip one.
        ParameterExpression row = Expression.Parameter(typeof(TRow), "row");
        Expression key = Rebind(_selector, row);
        Expression id = Rebind(_identity, row);
        Expression keyAnchor = Expression.Constant(lastKey, typeof(TKey));
        Expression idAnchor = Expression.Constant(anchor.Id, typeof(Guid));

        Expression keyBeyond = Compare(key, keyAnchor, direction);
        Expression keyEqual = Expression.Equal(key, keyAnchor);
        Expression idBeyond = Compare(id, idAnchor, direction);

        Expression predicate = Expression.OrElse(keyBeyond, Expression.AndAlso(keyEqual, idBeyond));

        return source.Where(Expression.Lambda<Func<TRow, bool>>(predicate, row));
    }

    /// <inheritdoc/>
    public KeysetAnchor AnchorOf(TRow row)
    {
        ArgumentNullException.ThrowIfNull(row);

        return new KeysetAnchor(_render(_readKey(row)), _readId(row));
    }

    private static Expression Rebind(LambdaExpression lambda, ParameterExpression parameter) =>
        new ParameterRebinder(lambda.Parameters[0], parameter).Visit(lambda.Body)
        ?? throw new InvalidOperationException("A sort selector rebound to nothing.");

    private static BinaryExpression Compare(Expression left, Expression right, KeysetDirection direction)
    {
        if (left.Type == typeof(string))
        {
            // string has no > operator; EF translates Compare into the provider's collation-aware
            // comparison, which is the same ordering OrderBy just used.
            MethodInfo compare = typeof(string).GetMethod(
                nameof(string.Compare),
                [typeof(string), typeof(string)])
                ?? throw new InvalidOperationException("string.Compare(string, string) not found.");

            Expression comparison = Expression.Call(compare, left, right);
            Expression zero = Expression.Constant(0);

            return direction == KeysetDirection.Ascending
                ? Expression.GreaterThan(comparison, zero)
                : Expression.LessThan(comparison, zero);
        }

        return direction == KeysetDirection.Ascending
            ? Expression.GreaterThan(left, right)
            : Expression.LessThan(left, right);
    }

    private sealed class ParameterRebinder : ExpressionVisitor
    {
        private readonly ParameterExpression _from;
        private readonly ParameterExpression _to;

        public ParameterRebinder(ParameterExpression from, ParameterExpression to)
        {
            _from = from;
            _to = to;
        }

        protected override Expression VisitParameter(ParameterExpression node) =>
            node == _from ? _to : base.VisitParameter(node);
    }
}

/// <summary>Renders and reads the values that go into a cursor.</summary>
/// <remarks>
/// Round-trip fidelity is the whole requirement. A timestamp rendered without its offset and full
/// sub-second precision produces a cursor that lands slightly off its own row, which shows up as a
/// listing that occasionally repeats or drops an entry — the hardest kind of paging bug to see.
/// </remarks>
public static class KeysetValues
{
    /// <summary>Renders a timestamp round-trippably.</summary>
    /// <param name="value">The timestamp.</param>
    /// <returns>An ISO-8601 round-trip rendering.</returns>
    public static string Render(DateTimeOffset value) =>
        value.ToString("O", CultureInfo.InvariantCulture);

    /// <summary>Reads a timestamp back.</summary>
    /// <param name="value">The rendered value.</param>
    /// <returns>The timestamp.</returns>
    /// <exception cref="FormatException">The value was not a round-trip timestamp.</exception>
    public static DateTimeOffset ParseTimestamp(string value) =>
        DateTimeOffset.ParseExact(value, "O", CultureInfo.InvariantCulture);

    /// <summary>Renders a nullable timestamp, using the empty string for null.</summary>
    /// <param name="value">The timestamp.</param>
    /// <returns>The rendering.</returns>
    public static string Render(DateTimeOffset? value) =>
        value is null ? string.Empty : Render(value.Value);

    /// <summary>Reads a nullable timestamp back.</summary>
    /// <param name="value">The rendered value.</param>
    /// <returns>The timestamp, or <see langword="null"/>.</returns>
    public static DateTimeOffset? ParseNullableTimestamp(string value) =>
        string.IsNullOrEmpty(value) ? null : ParseTimestamp(value);

    /// <summary>Renders a string value.</summary>
    /// <param name="value">The value.</param>
    /// <returns>The value unchanged.</returns>
    public static string Render(string value) => value;

    /// <summary>Reads a string value back.</summary>
    /// <param name="value">The rendered value.</param>
    /// <returns>The value unchanged.</returns>
    public static string ParseText(string value) => value;

    /// <summary>Renders an enum member by its numeric value, so cursor ordering matches the sort.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="value">The member.</param>
    /// <returns>The rendering.</returns>
    public static string RenderEnum<TEnum>(TEnum value)
        where TEnum : struct, Enum =>
        Convert.ToInt32(value, CultureInfo.InvariantCulture).ToString(CultureInfo.InvariantCulture);

    /// <summary>Reads an enum member back.</summary>
    /// <typeparam name="TEnum">The enum type.</typeparam>
    /// <param name="value">The rendered value.</param>
    /// <returns>The member.</returns>
    /// <exception cref="FormatException">The value was not an integer.</exception>
    public static TEnum ParseEnum<TEnum>(string value)
        where TEnum : struct, Enum =>
        (TEnum)Enum.ToObject(typeof(TEnum), int.Parse(value, CultureInfo.InvariantCulture));
}

/// <summary>Runs a keyset scan.</summary>
public static class KeysetQuery
{
    /// <summary>
    /// Reads one page, and reports where the next resumes.
    /// </summary>
    /// <remarks>
    /// Reads <c>limit + 1</c> rows and returns <c>limit</c>. A count query to decide whether more
    /// exist would double the work and still be a lie by the time the client acted on it; one extra
    /// row answers the only question a cursor client asks.
    /// </remarks>
    /// <typeparam name="TRow">The view row type.</typeparam>
    /// <param name="source">The already tenant-filtered query.</param>
    /// <param name="sortKey">The whitelisted sort field.</param>
    /// <param name="direction">Which way the scan runs.</param>
    /// <param name="anchor">Where to resume, or <see langword="null"/> for the first page.</param>
    /// <param name="limit">The clamped page size.</param>
    /// <param name="cancellationToken">Honoured before and during the query.</param>
    /// <returns>One page and its continuation.</returns>
    public static async Task<KeysetSlice<TRow>> TakeAsync<TRow>(
        IQueryable<TRow> source,
        IKeysetSortKey<TRow> sortKey,
        KeysetDirection direction,
        KeysetAnchor? anchor,
        int limit,
        CancellationToken cancellationToken)
        where TRow : class
    {
        ArgumentNullException.ThrowIfNull(source);
        ArgumentNullException.ThrowIfNull(sortKey);
        ArgumentOutOfRangeException.ThrowIfLessThan(limit, 1);

        IQueryable<TRow> query = source;

        if (anchor is not null)
        {
            query = sortKey.After(query, direction, anchor.Value);
        }

        List<TRow> rows = await sortKey
            .Order(query, direction)
            .Take(limit + 1)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        if (rows.Count <= limit)
        {
            return new KeysetSlice<TRow>(rows, null);
        }

        List<TRow> page = rows.GetRange(0, limit);

        return new KeysetSlice<TRow>(page, sortKey.AnchorOf(page[^1]));
    }
}
