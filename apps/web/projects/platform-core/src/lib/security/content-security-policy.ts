/**
 * The plan Stage 3 CSP baseline for the two browser surfaces.
 *
 * ## Delivered as a response header, never a `<meta>` tag
 *
 * This is the load-bearing detail. A policy in a `<meta>` tag sits in the document that injected
 * markup can reach, and several directives — `frame-ancestors`, `report-uri`, sandbox — are ignored
 * there entirely. A policy the page can strip is not a policy. `buildCspHeader` produces the value
 * for an HTTP response header; the hosting tier (or, for the desktop renderer, the Electron main
 * process via `csp.ts`) sets it, and the renderer cannot weaken it.
 *
 * `assertNoCspMetaTag` exists so the rule is testable from inside the app, since the mistake this
 * guards against is somebody "fixing" a CSP problem by adding the tag.
 *
 * ## `connect-src` is the load-bearing directive
 *
 * Exactly one platform origin (spec FR-SURF-017), the SignalR endpoint, and the Entra authority.
 * Nothing else. A surface that needs a directive loosened states why in review — particularly
 * `script-src`, where `'unsafe-eval'` would be required by a JIT Angular build, and is the reason
 * the build is AOT.
 */
export interface CspOrigins {
  /** The single gateway origin, e.g. `https://api.synthia.example`. */
  readonly gatewayOrigin: string;
  /** The SignalR endpoint, `wss://…`. */
  readonly signalROrigin: string;
  /** The Entra authority, normally `https://login.microsoftonline.com`. */
  readonly authAuthority: string;
}

export interface CspOptions {
  /**
   * Per-response nonce for Angular's injected styles.
   *
   * Angular emits component styles at runtime, so `style-src` needs either a nonce or
   * `'unsafe-inline'`. A nonce is the whole point: it must be freshly generated per response by the
   * tier that sets the header, and the same value given to Angular via `ngCspNonce`.
   */
  readonly styleNonce: string;
}

/**
 * Build the CSP header value.
 *
 * Returns a single-line policy suitable for `Content-Security-Policy`.
 */
export function buildCspHeader(origins: CspOrigins, options: CspOptions): string {
  if (options.styleNonce.trim().length === 0) {
    throw new Error(
      "A style nonce is required. Falling back to style-src 'unsafe-inline' would defeat the " +
        'policy, so it is not offered as an option.',
    );
  }

  const directives: readonly string[] = [
    `default-src 'self'`,
    // No 'unsafe-inline', no 'unsafe-eval', no CDN. AOT is what makes this possible.
    `script-src 'self'`,
    `style-src 'self' 'nonce-${options.styleNonce}'`,
    `img-src 'self' data:`,
    `font-src 'self'`,
    `connect-src 'self' ${origins.gatewayOrigin} ${origins.signalROrigin} ${origins.authAuthority}`,
    `frame-ancestors 'none'`,
    `form-action 'self'`,
    // 'self', NOT 'none', and the difference was found by sending the policy rather than reviewing
    // it. Every Angular document carries `<base href="/">`, which `base-uri 'none'` forbids
    // outright: both portals and the desktop renderer reported a violation on first paint. The
    // alternative — deleting the tag — makes a deep link resolve `main-<hash>.js` against
    // `/sessions/`, which 404s, so it would need the hosting tier to rewrite every asset URL.
    //
    // 'self' still refuses a <base> pointing at another origin, which is the attack: re-pointing
    // relative script loads at somewhere an attacker controls. It permits a same-origin one, which
    // needs injection into the document first — and injection is already what `script-src 'self'`,
    // the nonce and Angular's sanitisation exist to stop. Deviation from plan Stage 3, recorded
    // there with this reasoning.
    `base-uri 'self'`,
    `object-src 'none'`,
    'upgrade-insecure-requests',
  ];

  return directives.join('; ');
}

/** Directives the baseline must always contain, for tests and for review. */
export const REQUIRED_CSP_DIRECTIVES: readonly string[] = [
  'default-src',
  'script-src',
  'style-src',
  'img-src',
  'font-src',
  'connect-src',
  'frame-ancestors',
  'form-action',
  'base-uri',
  'object-src',
  'upgrade-insecure-requests',
];

/** Tokens that must never appear in the policy. */
export const FORBIDDEN_CSP_TOKENS: readonly string[] = ['unsafe-inline', 'unsafe-eval', '*'];

/**
 * Fail if the document declares a CSP in markup.
 *
 * The baseline is a response header. A `<meta http-equiv="Content-Security-Policy">` is either
 * redundant or a weaker second policy somebody added to make an error go away.
 */
export function assertNoCspMetaTag(doc: Document): void {
  const meta = doc.querySelector('meta[http-equiv="Content-Security-Policy" i]');
  if (meta !== null) {
    throw new Error(
      'CSP is delivered as a response header, never a <meta> tag: a policy in the document can be ' +
        'stripped by injected markup, and frame-ancestors is ignored there (plan Stage 3).',
    );
  }
}
