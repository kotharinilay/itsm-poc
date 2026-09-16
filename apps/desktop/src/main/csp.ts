/**
 * T054 — Content Security Policy for the renderer.
 *
 * The plan Stage 3 baseline, with `connect-src` narrowed identically, delivered from the **main
 * process** via `onHeadersReceived` so the renderer cannot weaken it. A policy the renderer emits
 * is a policy injected markup can strip; a policy the host attaches on every response is not.
 *
 * `connect-src` is the load-bearing directive: exactly one platform origin (spec FR-SURF-017), the
 * realtime origin, and the Entra authority. `script-src` carries no `'unsafe-eval'` — the Angular
 * build is AOT precisely so it does not need one.
 */

import { RENDERER_ORIGIN, RENDERER_SCHEME, type HostConfig } from './config.js';

/** The header name. Never `Content-Security-Policy-Report-Only` — this policy enforces. */
export const CSP_HEADER = 'Content-Security-Policy';

/** Directives that carry no origin and never vary with configuration. */
export const STATIC_DIRECTIVES: readonly string[] = Object.freeze([
  "default-src 'self'",
  // No 'unsafe-inline', no 'unsafe-eval', no CDN. The bundle is served from the app itself.
  "script-src 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  // The desktop host is not embeddable, in any frame, by anything.
  "frame-ancestors 'none'",
  "frame-src 'none'",
  "child-src 'none'",
  "worker-src 'self'",
  "form-action 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "manifest-src 'self'",
  // Belt and braces alongside the navigation allow-list: even a permitted navigation must be to
  // an origin this policy names.
  'upgrade-insecure-requests',
]);

/**
 * Build the policy for a configuration.
 *
 * `'unsafe-inline'` appears in **no** directive, including `style-src`. Angular injects component
 * styles as inline `<style>` elements at runtime, which is the usual reason a policy loosens here —
 * but this host serves the document itself (`renderer-protocol.ts`), so it can mint a per-response
 * nonce and hand it to Angular through `ngCspNonce`. Angular then stamps that nonce onto every
 * style element it injects, and the policy stays strict.
 *
 * A `nonce` of `null` produces the strict, nonce-free policy used for every response that is *not*
 * the renderer document. Nothing else needs to carry inline styles, so nothing else gets a nonce.
 *
 * Recorded in ADR-0006 (`docs/adr/0006-desktop-renderer-origin-and-csp-nonce.md`).
 */
export function buildContentSecurityPolicy(config: HostConfig, nonce: string | null = null): string {
  const connectSrc = [
    "connect-src 'self'",
    config.gatewayOrigin,
    config.realtimeOrigin,
    config.authorityOrigin,
  ].join(' ');

  const styleSrc = nonce === null ? "style-src 'self'" : `style-src 'self' 'nonce-${nonce}'`;

  return [
    ...STATIC_DIRECTIVES,
    styleSrc,
    connectSrc,
    // Only the app's own origin and the Entra authority may be navigated to from within the page.
    `navigate-to ${RENDERER_ORIGIN} ${config.authorityOrigin}`,
  ].join('; ');
}

/** Response headers, in Electron's `string[]` shape. */
export type ResponseHeaders = Record<string, string | string[]>;

/**
 * Replace any inbound CSP with ours.
 *
 * Case-insensitive removal first: HTTP header names are case-insensitive, and merging rather than
 * replacing would let a server-supplied policy *add* to ours — which, for CSP, means the
 * intersection is enforced but the directive list is no longer the one this file states. Removing
 * and setting keeps the policy exactly what is asserted in the security suite.
 */
export function withContentSecurityPolicy(
  headers: ResponseHeaders | undefined,
  config: HostConfig,
  nonce: string | null = null,
): ResponseHeaders {
  const next: ResponseHeaders = {};
  for (const [key, value] of Object.entries(headers ?? {})) {
    if (key.toLowerCase() === CSP_HEADER.toLowerCase()) {
      continue;
    }
    next[key] = value;
  }
  next[CSP_HEADER] = [buildContentSecurityPolicy(config, nonce)];
  return next;
}

/**
 * Whether the header interceptor should leave a response's policy alone.
 *
 * Exactly one response carries a nonce: the renderer document, whose policy is set at the source by
 * the protocol handler in `renderer-protocol.ts`. The interceptor cannot know that nonce, so
 * overwriting would strip it and block every style Angular injects.
 *
 * This is not a hole. Both the protocol handler and this interceptor are main-process code, and the
 * handler sets the policy on a single unconditional code path with no branch that can skip it —
 * `tests/security.spec.ts` asserts that. The renderer still cannot weaken anything: it does not
 * serve itself.
 */
export function isPolicySetAtSource(url: string): boolean {
  try {
    return new URL(url).protocol === RENDERER_SCHEME;
  } catch {
    // An unparseable URL is not the renderer document, so the interceptor applies the strict
    // policy — the fail-closed direction.
    return false;
  }
}

/** The slice of `Session` this module drives, so it can be wired without a real Electron session. */
export interface HeaderInterceptingSession {
  readonly webRequest: {
    onHeadersReceived(
      listener: (
        details: { url: string; responseHeaders?: ResponseHeaders },
        callback: (response: { responseHeaders: ResponseHeaders }) => void,
      ) => void,
    ): void;
  };
}

/**
 * Attach the strict policy to every response in a session, except the renderer document, whose
 * nonce-bearing policy is set at the source. See {@link isPolicySetAtSource}.
 */
export function applyContentSecurityPolicy(
  session: HeaderInterceptingSession,
  config: HostConfig,
): void {
  session.webRequest.onHeadersReceived((details, callback) => {
    if (isPolicySetAtSource(details.url)) {
      callback({ responseHeaders: details.responseHeaders ?? {} });
      return;
    }
    callback({ responseHeaders: withContentSecurityPolicy(details.responseHeaders, config) });
  });
}
