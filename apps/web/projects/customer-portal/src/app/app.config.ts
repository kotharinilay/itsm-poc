import {
  type ApplicationConfig,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { providePlatformCore } from 'platform-core';
import { routes } from './app.routes';
import { CUSTOMER_PORTAL_CONFIG } from './platform.config';

/**
 * Customer portal composition root.
 *
 * `providePlatformCore` is the whole of the shared infrastructure: the typed API clients, the
 * bearer token, correlation propagation, RFC 9457 handling and the browser security check. It is
 * called once, here — the constitution requires this infrastructure to be centralized rather than
 * repeated, and a surface that configured any of it separately would be the first crack in that.
 *
 * No state-management framework is adopted. Signals and the router cover the scaffold's needs, and
 * the constitution forbids adopting one unless a requirement justifies it.
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    providePlatformCore(CUSTOMER_PORTAL_CONFIG),
  ],
};
