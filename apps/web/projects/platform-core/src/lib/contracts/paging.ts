/**
 * Keyset/cursor paging, per contracts/README.md §Conventions.
 *
 * The cursor is **opaque to clients**: it is carried back verbatim and never parsed, decoded or
 * constructed here.
 */
export interface CursorPage<T> {
  readonly items: readonly T[];
  readonly nextCursor: string | null;
}

export interface CursorPageQuery {
  readonly limit?: number;
  readonly cursor?: string;
  /** `field` ascending, `-field` descending, over the allow-listed set for that resource. */
  readonly sort?: string;
}

/**
 * Sort direction is expressed in the field string, so this helper exists to build one correctly
 * rather than to parse one.
 */
export const descending = (field: string): string => `-${field}`;
export const ascending = (field: string): string => field;
