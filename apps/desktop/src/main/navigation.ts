/**
 * T053 — the navigation and new-window allow-list.
 *
 * Both `will-navigate` and `setWindowOpenHandler` deny by default. Plan Stage 4 names the complete
 * set of permitted destinations:
 *
 * | Destination                   | Why                                                    |
 * |-------------------------------|--------------------------------------------------------|
 * | The renderer's own bundle origin | The application itself                               |
 * | `https://{gateway-origin}`    | The single platform origin (spec FR-SURF-017)          |
 * | `https://login.microsoftonline.com` | Interactive Entra sign-in                         |
 * | `wss://{realtime-origin}`     | Notification and results only                          |
 *
 * Everything else is refused. Scheme matching is exact: for a *remote* destination, `https:` and
 * `wss:` only — never `http:`, never `file:`, never a custom scheme. The renderer's own origin is
 * checked by a separate predicate and is never treated as a remote destination, which is what
 * keeps it out of `shell.openExternal`.
 *
 * The functions here are pure so the security suite can assert them directly rather than having to
 * drive a real window. A control that can only be proven with a window is a control CI skips.
 */

import {
  ALLOWED_REMOTE_SCHEMES,
  EXTERNAL_SCHEME,
  originOf,
  RENDERER_ORIGIN,
  type HostConfig,
} from './config.js';

/** The complete remote allow-list for a given configuration, in the order plan Stage 4 lists it. */
export function allowedRemoteOrigins(config: HostConfig): readonly string[] {
  return Object.freeze([config.gatewayOrigin, config.authorityOrigin, config.realtimeOrigin]);
}

/**
 * Parse a URL, failing closed.
 *
 * Returns `null` for anything unparseable. Every caller treats `null` as "refuse", so a malformed
 * destination can never fall through to a permit.
 */
function parse(rawUrl: unknown): URL | null {
  if (typeof rawUrl !== 'string' || rawUrl === '') {
    return null;
  }
  try {
    return new URL(rawUrl);
  } catch {
    return null;
  }
}

/**
 * Is this URL the application's own renderer?
 *
 * Kept separate from the remote allow-list on purpose. The renderer origin is the app itself, not
 * a destination — it may be navigated to in-app and must **never** be handed to the OS handler.
 */
export function isRendererOrigin(rawUrl: unknown): boolean {
  const url = parse(rawUrl);
  return url !== null && originOf(url) === RENDERER_ORIGIN;
}

/**
 * Is this a permitted *remote* destination?
 *
 * Exact scheme match against `https:`/`wss:`, then exact origin match against the allow-list.
 * Origin comparison — not hostname, not `endsWith` — so `https://gateway.invalid.attacker.example`
 * is refused rather than matched as a suffix.
 */
export function isAllowedRemote(rawUrl: unknown, config: HostConfig): boolean {
  const url = parse(rawUrl);
  if (url === null) {
    return false;
  }
  if (!ALLOWED_REMOTE_SCHEMES.includes(url.protocol)) {
    return false;
  }
  return allowedRemoteOrigins(config).includes(originOf(url));
}

/**
 * May the window navigate here?
 *
 * The union of the app's own origin and the remote allow-list. This is the `will-navigate`
 * decision and nothing more — it decides where the window may point, never what the user may do
 * once it points there. That second question is the platform's and is re-decided server-side
 * (constitution Principle VII).
 */
export function isNavigationAllowed(rawUrl: unknown, config: HostConfig): boolean {
  return isRendererOrigin(rawUrl) || isAllowedRemote(rawUrl, config);
}

/**
 * May this URL be handed to the operating system's browser?
 *
 * Stricter than navigation, and deliberately so. `shell.openExternal` hands a string to the OS,
 * where a non-`https:` scheme can reach a protocol handler that runs something. So: `https:` only,
 * and only an origin already on the allow-list. Never the renderer's own origin, never `wss:`.
 */
export function isExternalOpenAllowed(rawUrl: unknown, config: HostConfig): boolean {
  const url = parse(rawUrl);
  if (url === null || url.protocol !== EXTERNAL_SCHEME) {
    return false;
  }
  return allowedRemoteOrigins(config).includes(originOf(url));
}

/** What the window-open handler decided, and why — returned so it can be asserted and logged. */
export interface WindowOpenDecision {
  /** Always `'deny'`. `setWindowOpenHandler` denies every destination without exception. */
  readonly action: 'deny';
  /** Whether the destination was additionally handed to the OS browser. */
  readonly openedExternally: boolean;
  readonly reason: 'opened-externally' | 'refused';
}

/**
 * Decide what to do with a `window.open` / target=_blank destination.
 *
 * The action is `'deny'` for **every** destination without exception — no Electron window is ever
 * created from page content. An allow-listed `https:` destination is additionally handed to the OS
 * browser, so nothing reaches the OS handler that could not have been navigated to in-app.
 */
export function decideWindowOpen(
  rawUrl: unknown,
  config: HostConfig,
  openExternal: (url: string) => void,
): WindowOpenDecision {
  if (typeof rawUrl === 'string' && isExternalOpenAllowed(rawUrl, config)) {
    openExternal(rawUrl);
    return { action: 'deny', openedExternally: true, reason: 'opened-externally' };
  }
  return { action: 'deny', openedExternally: false, reason: 'refused' };
}

/** The slice of `WebContents` this module drives, so the policy can be wired without Electron. */
export interface NavigableContents {
  on(
    event: 'will-navigate',
    listener: (event: { preventDefault(): void }, url: string) => void,
  ): unknown;
  on(
    event: 'will-redirect',
    listener: (event: { preventDefault(): void }, url: string) => void,
  ): unknown;
  setWindowOpenHandler(handler: (details: { url: string }) => { action: 'deny' }): unknown;
}

/**
 * Apply the policy to a `WebContents`.
 *
 * `will-redirect` is wired as well as `will-navigate`: a permitted origin that responds with a 302
 * to somewhere else is a navigation the first handler never sees.
 */
export function applyNavigationPolicy(
  contents: NavigableContents,
  config: HostConfig,
  openExternal: (url: string) => void,
): void {
  const refuseUnlessAllowed = (event: { preventDefault(): void }, url: string): void => {
    if (!isNavigationAllowed(url, config)) {
      event.preventDefault();
    }
  };

  contents.on('will-navigate', refuseUnlessAllowed);
  contents.on('will-redirect', refuseUnlessAllowed);
  contents.setWindowOpenHandler(({ url }) => {
    const decision = decideWindowOpen(url, config, openExternal);
    return { action: decision.action };
  });
}
