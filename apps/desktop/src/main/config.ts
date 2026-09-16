/**
 * Host configuration — the origins this desktop host is allowed to talk to.
 *
 * Configuration is read once, validated once, and frozen. Everything downstream — the navigation
 * allow-list, the CSP `connect-src`, the endpoints reported to the renderer — derives from this
 * one object, so there is a single place where a wrong origin can enter and a single place to
 * check when auditing where the client can reach.
 *
 * Validation is strict and fails closed. An origin that is not exactly a scheme-correct origin —
 * no path, no query, no credentials, no `http:` — is rejected at startup rather than silently
 * turning into a permissive allow-list entry at runtime.
 */

/** The renderer's own origin. See `renderer-protocol.ts` for why this is not `file://`. */
export const RENDERER_SCHEME = 'app:';
export const RENDERER_HOST = 'renderer';
export const RENDERER_ORIGIN = `${RENDERER_SCHEME}//${RENDERER_HOST}`;

/** Schemes a *remote* destination may use. Exact match, and nothing else is ever added here. */
export const ALLOWED_REMOTE_SCHEMES: readonly string[] = ['https:', 'wss:'];

/** The scheme a destination must use to be handed to the OS browser. Never `wss:`, never `app:`. */
export const EXTERNAL_SCHEME = 'https:';

/**
 * The origin of a parsed URL, as a string — or `'null'` for an opaque one.
 *
 * `URL.origin` cannot be used directly. The WHATWG parser only computes an origin for a *special*
 * scheme (`http`, `https`, `ws`, `wss`, `ftp`, `file`), and returns the string `'null'` for
 * everything else. Chromium *does* compute one for a scheme registered as standard — which `app:`
 * is, via `registerSchemesAsPrivileged` — but the pure functions in this package run under plain
 * Node in CI, where that registration has not happened.
 *
 * So the origin is computed here from scheme and host. A URL with no host has no origin and gets
 * `'null'`, which every caller treats as "refuse" — `file:///x` and `data:...` land there, as they
 * should.
 */
export function originOf(url: URL): string {
  if (url.origin !== 'null') {
    return url.origin;
  }
  return url.host === '' ? 'null' : `${url.protocol}//${url.host}`;
}

export interface HostConfig {
  /** The single platform origin (spec FR-SURF-017). Which backend serves a request is not a client concern. */
  readonly gatewayOrigin: string;
  /** The realtime origin. Notification and results only — never a link on a consequential path. */
  readonly realtimeOrigin: string;
  /** The Entra authority used for interactive sign-in. */
  readonly authorityOrigin: string;
}

export class HostConfigurationError extends Error {
  public override readonly name = 'HostConfigurationError';
}

/**
 * Parse a value that must be exactly an origin on one of `schemes`.
 *
 * Rejects anything carrying a path, query, fragment, username or password. `https://gateway/../x`
 * and `https://user:pass@gateway` both normalise to an origin that would then be allow-listed,
 * and neither is something a correct configuration ever contains.
 */
export function parseOrigin(raw: string, schemes: readonly string[], label: string): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new HostConfigurationError(`${label} is not a URL: ${JSON.stringify(raw)}`);
  }

  if (!schemes.includes(url.protocol)) {
    throw new HostConfigurationError(
      `${label} must use ${schemes.join(' or ')} — got ${url.protocol}`,
    );
  }
  if (url.username !== '' || url.password !== '') {
    throw new HostConfigurationError(`${label} must not carry credentials`);
  }
  if (url.search !== '' || url.hash !== '') {
    throw new HostConfigurationError(`${label} must be a bare origin, with no query or fragment`);
  }
  if (url.pathname !== '/' && url.pathname !== '') {
    throw new HostConfigurationError(`${label} must be a bare origin, with no path`);
  }
  const origin = originOf(url);
  if (origin === 'null') {
    throw new HostConfigurationError(`${label} has an opaque origin`);
  }
  return origin;
}

/** The environment variables the host reads. Named here so the set is greppable. */
export const CONFIG_ENV_KEYS = {
  gatewayOrigin: 'SYNTHIA_GATEWAY_ORIGIN',
  realtimeOrigin: 'SYNTHIA_REALTIME_ORIGIN',
  authorityOrigin: 'SYNTHIA_AUTHORITY_ORIGIN',
} as const;

/**
 * Defaults.
 *
 * `.invalid` is reserved by RFC 6761 and can never resolve. An unconfigured build therefore fails
 * to reach anything rather than reaching something — which is the correct behaviour for a default,
 * and is why there is no `localhost` fallback here.
 */
export const DEFAULT_CONFIG: HostConfig = Object.freeze({
  gatewayOrigin: 'https://gateway.synthia.invalid',
  realtimeOrigin: 'wss://realtime.synthia.invalid',
  authorityOrigin: 'https://login.microsoftonline.com',
});

/** Build and validate a host configuration from an environment-like record. */
export function loadHostConfig(
  env: Readonly<Record<string, string | undefined>> = process.env,
): HostConfig {
  const gatewayOrigin = parseOrigin(
    env[CONFIG_ENV_KEYS.gatewayOrigin] ?? DEFAULT_CONFIG.gatewayOrigin,
    ['https:'],
    CONFIG_ENV_KEYS.gatewayOrigin,
  );
  const realtimeOrigin = parseOrigin(
    env[CONFIG_ENV_KEYS.realtimeOrigin] ?? DEFAULT_CONFIG.realtimeOrigin,
    ['wss:'],
    CONFIG_ENV_KEYS.realtimeOrigin,
  );
  const authorityOrigin = parseOrigin(
    env[CONFIG_ENV_KEYS.authorityOrigin] ?? DEFAULT_CONFIG.authorityOrigin,
    ['https:'],
    CONFIG_ENV_KEYS.authorityOrigin,
  );

  return Object.freeze({ gatewayOrigin, realtimeOrigin, authorityOrigin });
}
