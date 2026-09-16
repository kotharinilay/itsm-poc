/**
 * Renderer integration — how the Angular `desktop-renderer` bundle reaches the window.
 *
 * ## Why not `file://`
 *
 * The constitution says `file://` is "avoided where a safer protocol strategy applies"
 * (Principle VII). This is that case, and it is not a stylistic preference — three controls in
 * this scaffold do not function over `file://`:
 *
 *  - **CSP.** A `file://` document has an *opaque* origin, so `'self'` matches nothing. The policy
 *    the host attaches in `csp.ts` would be enforced against an origin that can never satisfy it.
 *  - **IPC sender validation.** `new URL('file:///x').origin` is the string `'null'`. There is no
 *    origin to allow-list, so `isSenderTrusted` could only ever be a path-prefix check — which is
 *    a string comparison against attacker-influenced input, not an origin check.
 *  - **Fetch to the gateway.** Requests from an opaque origin are `Origin: null`, which the
 *    platform cannot distinguish from any other opaque origin.
 *
 * So the bundle is served over a custom scheme registered as **standard** and **secure**, giving
 * the renderer a real, stable origin (`app://renderer`). Plan Stage 4's "never a custom scheme"
 * governs the *navigation allow-list* — the set of remote destinations the window may point at —
 * and `navigation.ts` honours it exactly: `https:` and `wss:` only for anything remote. The app's
 * own origin is a separate predicate there and is never handed to `shell.openExternal`.
 *
 * **This divergence from plan Stage 4's prose is recorded in ADR-0006**
 * (`docs/adr/0006-desktop-renderer-origin-and-csp-nonce.md`). Reverting to `file://` silently
 * disables the three controls above while leaving their tests green, so it is an ADR amendment
 * rather than a code change.
 *
 * ## Containment
 *
 * `resolveBundlePath` is the security-relevant function in this file. It maps a URL path to a file
 * inside the bundle directory and refuses anything that escapes it. It is pure, so
 * `tests/renderer-protocol.spec.ts` can throw traversal payloads at it directly.
 */

import { randomBytes } from 'node:crypto';
import path from 'node:path';

import { originOf, RENDERER_HOST, RENDERER_ORIGIN, RENDERER_SCHEME } from './config.js';

/** The scheme registration Electron needs, before `app.whenReady()`. */
export const RENDERER_SCHEME_PRIVILEGES = Object.freeze({
  /** Without the scheme name, no privileges apply. `app:` without the trailing colon. */
  scheme: RENDERER_SCHEME.replace(':', ''),
  privileges: Object.freeze({
    /** A standard scheme has a parsable origin — the whole point of the exercise. */
    standard: true,
    /** Treated as a secure context: enables the same restrictions an HTTPS page gets. */
    secure: true,
    /** Subject to CSP, so the policy in `csp.ts` actually applies. */
    supportFetchAPI: true,
    /** Same-origin policy applies normally. Never bypassed. */
    corsEnabled: true,
    /** No stream loading needed; the bundle is small static files. */
    stream: false,
    /** This scheme does NOT get universal access. It is an ordinary origin. */
    allowServiceWorkers: false,
  }),
});

/** The SPA entry document. Every non-file path resolves here so client-side routing works. */
export const INDEX_DOCUMENT = 'index.html';

export class RendererPathError extends Error {
  public override readonly name = 'RendererPathError';
}

/**
 * Map a request URL to an absolute path inside the bundle directory.
 *
 * Refuses, rather than clamping, anything that escapes `bundleRoot` — a traversal attempt is a
 * signal worth surfacing, not something to quietly normalise away.
 *
 * Containment is checked **after** `path.resolve`, on the resolved absolute path, because that is
 * the only form in which `..`, encoded separators, absolute paths and (on Windows) drive-relative
 * paths have all already collapsed. Checking the raw string first would be checking a different
 * value than the one that eventually opens a file.
 */
export function resolveBundlePath(bundleRoot: string, requestUrl: string): string {
  let url: URL;
  try {
    url = new URL(requestUrl);
  } catch {
    throw new RendererPathError(`Unparseable renderer request: ${JSON.stringify(requestUrl)}`);
  }

  if (url.protocol !== RENDERER_SCHEME || url.host !== RENDERER_HOST) {
    throw new RendererPathError(`Renderer request outside ${RENDERER_ORIGIN}: ${originOf(url)}`);
  }

  // Percent-decoding must happen before containment, or `%2e%2e%2f` is checked as a literal.
  let decoded: string;
  try {
    decoded = decodeURIComponent(url.pathname);
  } catch {
    throw new RendererPathError('Renderer request has an invalid percent-encoding');
  }

  // A NUL truncates the path at the syscall boundary while looking harmless above it.
  if (decoded.includes('\0')) {
    throw new RendererPathError('Renderer request contains a NUL byte');
  }

  const root = path.resolve(bundleRoot);
  // Strip the leading '/' so `path.resolve` treats the remainder as relative to the bundle root
  // rather than as an absolute path that would replace it.
  const relative = decoded.replace(/^\/+/, '');
  const candidate = path.resolve(root, relative === '' ? INDEX_DOCUMENT : relative);

  const contained =
    candidate === root || candidate.startsWith(root + path.sep);
  if (!contained) {
    throw new RendererPathError(`Renderer request escapes the bundle: ${decoded}`);
  }

  return candidate;
}

/**
 * Decide what to serve for a request.
 *
 * A path with no file extension is an Angular client-side route, so the entry document is served
 * and the router takes over. A path *with* an extension that does not exist is a genuine 404 and
 * is not masked by falling back to `index.html` — masking it would turn every mistyped asset URL
 * into a silently successful HTML response.
 */
export function chooseRendererResponse(
  bundleRoot: string,
  requestUrl: string,
  exists: (filePath: string) => boolean,
): { readonly filePath: string; readonly isEntryDocument: boolean } {
  const resolved = resolveBundlePath(bundleRoot, requestUrl);
  if (exists(resolved)) {
    return { filePath: resolved, isEntryDocument: resolved === path.resolve(bundleRoot, INDEX_DOCUMENT) };
  }

  const hasExtension = path.extname(resolved) !== '';
  if (hasExtension) {
    throw new RendererPathError(`Renderer asset not found: ${path.basename(resolved)}`);
  }

  return { filePath: path.resolve(bundleRoot, INDEX_DOCUMENT), isEntryDocument: true };
}

/** The URL the window loads at startup. */
export const RENDERER_ENTRY_URL = `${RENDERER_ORIGIN}/${INDEX_DOCUMENT}`;

// ---------------------------------------------------------------------------------------------
// CSP nonce
//
// Because the host serves the document itself, it can mint a nonce per response and hand it to
// Angular. That is what keeps `'unsafe-inline'` out of `style-src` entirely — see `csp.ts`.
// ---------------------------------------------------------------------------------------------

/** 128 bits, base64. CSP nonces must be unpredictable, so this uses the CSPRNG, never `Math.random`. */
export function createNonce(): string {
  return randomBytes(16).toString('base64');
}

/**
 * Stamp a nonce onto the entry document.
 *
 * Two things happen, and both are needed:
 *
 *  - `ngCspNonce` on `<app-root>`. Angular reads this at bootstrap and applies it to every `<style>`
 *    element it injects for a component at runtime, which is where the inline styles actually come
 *    from.
 *  - `nonce` on any `<style>` element already in the document. The Angular builder's critical-CSS
 *    inlining can put one there, and it would otherwise be blocked.
 *
 * Inline `<script>` is deliberately **not** noncing. `script-src` stays `'self'` with no nonce, so
 * an inline script is blocked — which is the correct outcome, and a loud one.
 */
export function injectNonce(html: string, nonce: string): string {
  return html
    .replace(/<app-root(?=[\s>])/gi, `<app-root ngCspNonce="${nonce}"`)
    .replace(/<style(?=[\s>])/gi, `<style nonce="${nonce}"`);
}

/** Whether a resolved path is the entry document, and therefore needs a nonce. */
export function isEntryDocument(bundleRoot: string, filePath: string): boolean {
  return path.resolve(filePath) === path.resolve(bundleRoot, INDEX_DOCUMENT);
}
