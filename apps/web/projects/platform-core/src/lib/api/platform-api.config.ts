import { InjectionToken } from '@angular/core';

/**
 * Runtime configuration for every platform call.
 *
 * **No secret belongs in this object, or anywhere else in browser code** (constitution §Secrets).
 * Everything here is a public origin or a path. There is no client secret, no API key and no
 * connection string, because a browser cannot keep one — anything shipped to the page is readable
 * by whoever loads the page.
 */
export interface PlatformApiConfig {
  /**
   * The single gateway origin. Spec FR-SURF-017: a client MUST address the platform through one
   * gateway, and MUST NOT be configured with more than one platform origin. Which backend serves a
   * given operation is not a client concern — hence one field, not two.
   */
  readonly gatewayOrigin: string;

  /** Entra authority used by the auth integration. A public URL, not a credential. */
  readonly authAuthority: string;

  /** Public application (client) id. Public by definition in a browser flow — never a secret. */
  readonly authClientId: string;

  /** Scopes requested for platform access tokens. */
  readonly authScopes: readonly string[];
}

export const PLATFORM_API_CONFIG = new InjectionToken<PlatformApiConfig>('PLATFORM_API_CONFIG');

/** Patterns that must never appear in a configuration value shipped to a browser. */
const SECRET_KEYS = [
  'secret',
  'clientsecret',
  'password',
  'apikey',
  'connectionstring',
  'privatekey',
  'accountkey',
  'sastoken',
];

/**
 * Reject a configuration that carries something a browser cannot keep.
 *
 * This runs at bootstrap so the failure is loud and immediate rather than a finding in a later
 * review. It also enforces the single-origin rule while it is here.
 */
export function assertConfigCarriesNoSecret(config: PlatformApiConfig): void {
  for (const key of Object.keys(config)) {
    const normalised = key.toLowerCase().replace(/[^a-z]/g, '');
    if (SECRET_KEYS.some((forbidden) => normalised.includes(forbidden))) {
      throw new Error(
        `PlatformApiConfig.${key} looks like a secret. No credential may be shipped in browser ` +
          `code (constitution §Secrets). Obtain tokens through the auth integration instead.`,
      );
    }
  }

  assertAbsoluteHttpsOrigin(config.gatewayOrigin, 'gatewayOrigin');
  assertAbsoluteHttpsOrigin(config.authAuthority, 'authAuthority');
}

function assertAbsoluteHttpsOrigin(value: string, field: string): void {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`PlatformApiConfig.${field} must be an absolute URL. Received: ${value}`);
  }

  // `http:` is permitted only for localhost during development; everything else must be HTTPS so
  // the CSP `upgrade-insecure-requests` directive never has anything to upgrade.
  const isLocalhost = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && isLocalhost)) {
    throw new Error(`PlatformApiConfig.${field} must use https. Received: ${value}`);
  }
}
