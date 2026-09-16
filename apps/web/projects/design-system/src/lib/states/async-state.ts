import type { PresentableFailure } from './presentable-failure';

/**
 * The single vocabulary every surface uses to describe an in-flight read.
 *
 * `empty` and `failed` are deliberately distinct members. Spec FR-SURF-016 requires that a failure
 * MUST NOT be presented as an empty result, and the cheapest way to break that rule is to model
 * both as "no items". They are not the same state and this union will not let them collapse.
 *
 * `partial` exists for the same reason: a read that returned some data *and* failed is neither
 * `ready` nor `failed`, and flattening it to either one loses information a person needs.
 */
export type AsyncState<T, E = PresentableFailure> =
  | { readonly status: 'idle' }
  | { readonly status: 'loading' }
  | { readonly status: 'empty' }
  | { readonly status: 'ready'; readonly value: T }
  | { readonly status: 'partial'; readonly value: T; readonly failure: E }
  | { readonly status: 'failed'; readonly failure: E };

export type AsyncStatus = AsyncState<unknown>['status'];

export const idle = <T, E = PresentableFailure>(): AsyncState<T, E> => ({ status: 'idle' });
export const loading = <T, E = PresentableFailure>(): AsyncState<T, E> => ({ status: 'loading' });
export const empty = <T, E = PresentableFailure>(): AsyncState<T, E> => ({ status: 'empty' });

export const ready = <T, E = PresentableFailure>(value: T): AsyncState<T, E> => ({
  status: 'ready',
  value,
});

export const partial = <T, E = PresentableFailure>(value: T, failure: E): AsyncState<T, E> => ({
  status: 'partial',
  value,
  failure,
});

export const failed = <T, E = PresentableFailure>(failure: E): AsyncState<T, E> => ({
  status: 'failed',
  failure,
});

/**
 * Build the state for a completed list read, choosing `empty` over `ready` for a zero-length result.
 * Failure never routes here — that is the point.
 */
export function readyOrEmpty<T, E = PresentableFailure>(
  items: readonly T[],
): AsyncState<readonly T[], E> {
  return items.length === 0 ? empty<readonly T[], E>() : ready<readonly T[], E>(items);
}

export const isPending = <T, E>(state: AsyncState<T, E>): boolean => state.status === 'loading';

/** True for `failed` and `partial`. A `partial` read has failed at something, even though it has data. */
export const hasFailure = <T, E>(state: AsyncState<T, E>): boolean =>
  state.status === 'failed' || state.status === 'partial';

export function failureOf<T, E>(state: AsyncState<T, E>): E | undefined {
  return state.status === 'failed' || state.status === 'partial' ? state.failure : undefined;
}

export function valueOf<T, E>(state: AsyncState<T, E>): T | undefined {
  return state.status === 'ready' || state.status === 'partial' ? state.value : undefined;
}
