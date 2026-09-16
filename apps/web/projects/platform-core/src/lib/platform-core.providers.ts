import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  type EnvironmentProviders,
  makeEnvironmentProviders,
  provideAppInitializer,
} from '@angular/core';
import {
  PLATFORM_API_CONFIG,
  type PlatformApiConfig,
  assertConfigCarriesNoSecret,
} from './api/platform-api.config';
import {
  authInterceptor,
  correlationInterceptor,
  problemDetailsInterceptor,
} from './api/platform.interceptors';
import { verifyBrowserSecurityBaseline } from './security/sanitization-policy';

/**
 * Wire the shared client infrastructure into a surface.
 *
 * One call, in one place per application. Centralising it is what makes "authentication, API and
 * realtime infrastructure are each centralized rather than repeated" (constitution §Angular) true
 * of the workspace rather than aspirational: a surface cannot half-configure this, and cannot
 * quietly add a second platform origin.
 *
 * Interceptor order is deliberate:
 *  1. `correlationInterceptor` — stamps the id, so everything downstream can log it;
 *  2. `authInterceptor` — attaches the bearer token to gateway requests only;
 *  3. `problemDetailsInterceptor` — outermost on the response path, so it sees failures from both.
 */
export function providePlatformCore(config: PlatformApiConfig): EnvironmentProviders {
  // Fails at bootstrap, not in review: a browser cannot keep a secret, and a second platform
  // origin would break FR-SURF-017.
  assertConfigCarriesNoSecret(config);

  return makeEnvironmentProviders([
    { provide: PLATFORM_API_CONFIG, useValue: config },
    provideHttpClient(
      withInterceptors([correlationInterceptor, authInterceptor, problemDetailsInterceptor]),
    ),
    provideAppInitializer(() => {
      verifyBrowserSecurityBaseline();
    }),
  ]);
}
