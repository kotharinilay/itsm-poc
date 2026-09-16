import type { PresentableFailure } from 'design-system';

/**
 * The only error type features see from a platform call.
 *
 * It carries a `PresentableFailure` the design system can render directly, so no feature has to
 * translate a status code into a message and none of them can do it inconsistently.
 */
export class PlatformApiError extends Error {
  constructor(
    readonly failure: PresentableFailure,
    readonly status: number,
  ) {
    super(failure.title);
    this.name = 'PlatformApiError';
  }
}

export function isPlatformApiError(error: unknown): error is PlatformApiError {
  return error instanceof PlatformApiError;
}
