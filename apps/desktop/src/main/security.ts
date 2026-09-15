/**
 * Electron security configuration.
 *
 * Every value here is a security control the constitution states as a requirement
 * (Principle VII) and plan Stage 4 resolves to a concrete value. They are exported as data,
 * not applied inline, so `tests/security.spec.ts` can assert each one and fail when it is
 * flipped — a protection without a failing test does not count.
 *
 * The endpoint runs inside a customer network and is outside platform control. Anything it
 * decides is a decision an attacker can make instead.
 */

import type { BrowserWindowConstructorOptions } from 'electron';

/**
 * The single platform origin the client is configured with (spec FR-SURF-017). Which backend
 * serves a given operation is not a client concern.
 */
export const GATEWAY_ORIGIN = process.env['SYNTHIA_GATEWAY_ORIGIN'] ?? 'https://gateway.invalid';

/** The Entra authority used for interactive sign-in. */
export const ENTRA_AUTHORITY = 'https://login.microsoftonline.com';

/**
 * Navigation allow-list — the complete set (plan Stage 4).
 *
 * Anything not listed is refused. Scheme matching is exact: `https:` and `wss:` only, never
 * `http:`, `file:` or a custom scheme.
 */
export const ALLOWED_NAVIGATION_ORIGINS: readonly string[] = [GATEWAY_ORIGIN, ENTRA_AUTHORITY];

/** Schemes that may be navigated to at all. */
export const ALLOWED_SCHEMES: readonly string[] = ['https:', 'wss:'];

/**
 * `webPreferences` for every window.
 *
 * `sandbox` is **unconditional** in this application. The constitution says "where compatible";
 * plan Stage 4 resolves that discretion here, because the one thing that breaks sandbox — a
 * preload needing Node built-ins — does not apply to a preload that exposes a narrow typed
 * bridge and nothing else. Turning it off requires an ADR, not a code comment.
 */
export const SECURE_WEB_PREFERENCES: BrowserWindowConstructorOptions['webPreferences'] = {
  nodeIntegration: false,
  nodeIntegrationInWorker: false,
  nodeIntegrationInSubFrames: false,
  contextIsolation: true,
  sandbox: true,
  webSecurity: true,
  allowRunningInsecureContent: false,
  experimentalFeatures: false,
  webviewTag: false,
};

/**
 * Content Security Policy — the plan Stage 3 baseline, applied to the renderer from the main
 * process so the renderer cannot weaken it.
 *
 * `connect-src` is the load-bearing directive: exactly one platform origin, plus the Entra
 * authority. `script-src` carries no `'unsafe-eval'` — the build is AOT precisely so it does
 * not need one.
 */
export function buildContentSecurityPolicy(): string {
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self' ${GATEWAY_ORIGIN} ${ENTRA_AUTHORITY}`,
    "frame-ancestors 'none'",
    "form-action 'self'",
    "base-uri 'none'",
    "object-src 'none'",
    'upgrade-insecure-requests',
  ].join('; ');
}

/**
 * Decide whether a URL may be navigated to.
 *
 * Fails closed: an unparseable URL, a disallowed scheme, or an origin outside the allow-list is
 * refused. This is a pure function so the security suite can assert it directly rather than
 * having to drive a real window.
 */
export function isNavigationAllowed(rawUrl: string): boolean {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return false;
  }

  if (!ALLOWED_SCHEMES.includes(url.protocol)) {
    return false;
  }

  return ALLOWED_NAVIGATION_ORIGINS.includes(url.origin);
}
