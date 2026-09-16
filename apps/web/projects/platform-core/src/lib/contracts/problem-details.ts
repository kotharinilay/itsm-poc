import { type FailureKind, type PresentableFailure, presentableFailure } from 'design-system';

/**
 * RFC 9457 `application/problem+json`, the error shape both deployables return
 * (contracts/README.md §Conventions binding every endpoint).
 */
export interface ProblemDetails {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail?: string;
  readonly instance?: string;
  readonly correlationId?: string;
}

export const PROBLEM_JSON = 'application/problem+json';

export function isProblemDetails(body: unknown): body is ProblemDetails {
  if (typeof body !== 'object' || body === null) {
    return false;
  }
  const candidate = body as Record<string, unknown>;
  return typeof candidate['title'] === 'string' && typeof candidate['status'] === 'number';
}

function kindForStatus(status: number): FailureKind {
  switch (status) {
    case 0:
      return 'network';
    case 401:
      return 'unauthenticated';
    case 403:
      return 'forbidden';
    // 404 is also what the platform returns when existence itself is tenant-scoped information
    // (contracts/README.md). The client cannot tell the two apart, and must not try.
    case 404:
      return 'not-found';
    case 408:
    case 504:
      return 'timeout';
    case 409:
      return 'conflict';
    default:
      return status >= 500 ? 'server' : 'unknown';
  }
}

/**
 * Map a transport failure onto the presentation-level failure the design system renders.
 *
 * The server's `detail` is surfaced only for statuses where it describes the request rather than
 * the platform's internals; a 5xx `detail` is replaced, so an internal message cannot leak into the
 * page.
 */
export function toPresentableFailure(
  status: number,
  body: unknown,
  fallbackCorrelationId?: string,
): PresentableFailure {
  const kind = kindForStatus(status);
  const problem = isProblemDetails(body) ? body : null;

  const title =
    kind === 'server'
      ? 'The platform could not complete this request'
      : (problem?.title ?? defaultTitle(kind));

  const detail = kind === 'server' ? undefined : problem?.detail;
  const correlation = problem?.correlationId ?? fallbackCorrelationId;

  return presentableFailure(kind, title, {
    detail,
    correlationId: correlation,
  });
}

function defaultTitle(kind: FailureKind): string {
  switch (kind) {
    case 'network':
      return 'Cannot reach the platform';
    case 'timeout':
      return 'The platform took too long to respond';
    case 'unauthenticated':
      return 'Please sign in again';
    case 'forbidden':
      return 'You do not have access to this';
    case 'not-found':
      return 'Not found';
    case 'conflict':
      return 'This has already changed';
    case 'server':
      return 'The platform could not complete this request';
    case 'unknown':
      return 'Something went wrong';
  }
}
