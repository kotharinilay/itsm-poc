/**
 * The presentation-level shape of a failure.
 *
 * `design-system` is the dependency floor: it cannot know about RFC 9457 problem details, HTTP, or
 * any transport. `platform-core` maps a `ProblemDetails` response onto this type, so the states
 * below can render a failure without the floor ever depending on the layer above it.
 */
export type FailureKind =
  | 'network'
  | 'timeout'
  | 'unauthenticated'
  | 'forbidden'
  | 'not-found'
  | 'conflict'
  | 'server'
  | 'unknown';

export interface PresentableFailure {
  readonly kind: FailureKind;
  /** Short, human-readable summary. Never raw provider text. */
  readonly title: string;
  /** Optional elaboration. Never a stack trace and never a credential. */
  readonly detail?: string;
  /**
   * Carried so a person can quote it to support. It correlates a request to audit; it is not
   * authority-bearing and grants nothing.
   */
  readonly correlationId?: string;
  /** Whether re-issuing the same request could plausibly succeed. */
  readonly retryable: boolean;
}

const RETRYABLE: ReadonlySet<FailureKind> = new Set<FailureKind>(['network', 'timeout', 'server']);

export function isRetryableKind(kind: FailureKind): boolean {
  return RETRYABLE.has(kind);
}

/** Build a failure without tripping `exactOptionalPropertyTypes` on absent fields. */
export function presentableFailure(
  kind: FailureKind,
  title: string,
  extra: { detail?: string | undefined; correlationId?: string | undefined } = {},
): PresentableFailure {
  return {
    kind,
    title,
    retryable: isRetryableKind(kind),
    ...(extra.detail === undefined ? {} : { detail: extra.detail }),
    ...(extra.correlationId === undefined ? {} : { correlationId: extra.correlationId }),
  };
}
