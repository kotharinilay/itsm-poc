import { type HttpErrorResponse, type HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, take, throwError } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { CORRELATION_HEADER, CorrelationService } from './correlation';
import { PLATFORM_API_CONFIG } from './platform-api.config';
import { PlatformApiError } from './platform-api-error';
import { toPresentableFailure } from '../contracts/problem-details';

/**
 * Stamp `X-Correlation-Id` on every platform request.
 *
 * Applied centrally so it cannot be forgotten by a caller. A request the edge sees without one is a
 * request nobody can trace through triggers, notifications, logs, spans and audit.
 */
export const correlationInterceptor: HttpInterceptorFn = (request, next) => {
  const config = inject(PLATFORM_API_CONFIG);
  if (!request.url.startsWith(config.gatewayOrigin)) {
    return next(request);
  }

  if (request.headers.has(CORRELATION_HEADER)) {
    return next(request);
  }

  const correlation = inject(CorrelationService).next();
  return next(request.clone({ setHeaders: { [CORRELATION_HEADER]: correlation } }));
};

/**
 * Attach the bearer token to platform requests, and only to platform requests.
 *
 * The origin check is the point: a token minted for the platform audience is never sent anywhere
 * else, so a mistyped URL or a third-party asset cannot receive it.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const config = inject(PLATFORM_API_CONFIG);
  if (!request.url.startsWith(config.gatewayOrigin)) {
    return next(request);
  }

  return inject(AuthService)
    .accessToken()
    .pipe(
      take(1),
      switchMap((token) =>
        next(
          token === null
            ? request
            : request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }),
        ),
      ),
    );
};

/**
 * Turn every transport failure into a `PlatformApiError` carrying a renderable failure.
 *
 * Centralised so no feature has to know about RFC 9457, HTTP status codes, or the difference
 * between "the server said no" and "the network did not arrive". Features consume a
 * `PresentableFailure` and render it; they never branch on a status code.
 */
export const problemDetailsInterceptor: HttpInterceptorFn = (request, next) => {
  const config = inject(PLATFORM_API_CONFIG);
  if (!request.url.startsWith(config.gatewayOrigin)) {
    return next(request);
  }

  return next(request).pipe(
    catchError((error: unknown) => {
      if (!isHttpErrorResponse(error)) {
        return throwError(() => error);
      }

      const correlation = error.headers.get(CORRELATION_HEADER) ?? undefined;
      const failure = toPresentableFailure(error.status, error.error, correlation);
      return throwError(() => new PlatformApiError(failure, error.status));
    }),
  );
};

function isHttpErrorResponse(error: unknown): error is HttpErrorResponse {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    'headers' in error &&
    typeof (error as { status: unknown }).status === 'number'
  );
}
