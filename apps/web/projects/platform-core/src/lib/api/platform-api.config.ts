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
  assertNoSecretKeys(config);

  assertAbsoluteHttpsOrigin(config.gatewayOrigin, 'gatewayOrigin');
  assertAbsoluteHttpsOrigin(config.authAuthority, 'authAuthority');
}

/**
 * Reject any key that names something a browser cannot keep.
 *
 * Separate from the origin checks because it applies to a **partial** configuration too: what the
 * hosting tier supplies is merged field by field, so a secret in it would otherwise be dropped
 * silently rather than refused. Dropping it is safe and says nothing; a tier that ships a client
 * secret has made a mistake somebody needs to hear about.
 */
function assertNoSecretKeys(candidate: object): void {
  for (const key of Object.keys(candidate)) {
    const normalised = key.toLowerCase().replace(/[^a-z]/g, '');
    if (SECRET_KEYS.some((forbidden) => normalised.includes(forbidden))) {
      throw new Error(
        `PlatformApiConfig.${key} looks like a secret. No credential may be shipped in browser ` +
          `code (constitution §Secrets). Obtain tokens through the auth integration instead.`,
      );
    }
  }
}

/** Where the hosting tier puts the configuration it supplies (ADR-0009). */
export const HOSTED_CONFIG_ELEMENT_ID = 'synthia-platform-config';

/**
 * The configuration this deployment was given, or the compiled fallback.
 *
 * **A bundle cannot carry its own environment.** The same image is promoted from one environment to
 * the next by digest, so the gateway origin and the Entra client id cannot be baked in at build
 * time — the build would be per-environment and the artefact reviewed in one would not be the one
 * running in another. The hosting tier writes them into the document it serves
 * (`apps/web/scripts/csp-host.mjs`) and this reads them back.
 *
 * **A JSON data block, never executable script.** `<script type="application/json">` is not run by
 * the browser, so it needs no CSP nonce and cannot become an injection vector: the worst a bad
 * value can do is fail the assertions below, loudly, at bootstrap.
 *
 * **The fallback is the development default, and it is deliberate.** Running `ng serve` or the
 * reference host with no environment supplies no block, and the portal then points where the
 * compiled config says — which for a developer is the local gateway.
 *
 * @param doc The document to read. Passed rather than reached for, so it is testable.
 * @param fallback The compiled configuration, used when the tier supplied none.
 * @returns The configuration to bootstrap with. Validated either way.
 */
export function readHostedConfig(doc: Document, fallback: PlatformApiConfig): PlatformApiConfig {
  const element = doc.getElementById(HOSTED_CONFIG_ELEMENT_ID);
  if (element === null || element.textContent === null || element.textContent.trim() === '') {
    assertConfigCarriesNoSecret(fallback);
    return fallback;
  }

  let supplied: Partial<PlatformApiConfig>;
  try {
    supplied = JSON.parse(element.textContent) as Partial<PlatformApiConfig>;
  } catch (cause) {
    // Loud, at bootstrap. A portal that silently fell back would point at the developer default
    // in a deployed environment, which is the failure this whole mechanism exists to prevent.
    throw new Error(
      `The hosting tier supplied a malformed ${HOSTED_CONFIG_ELEMENT_ID} document: ${String(cause)}`,
    );
  }

  // Checked before the merge, which keeps only the four known fields: a secret in the supplied
  // document would otherwise be discarded quietly instead of refused.
  assertNoSecretKeys(supplied);

  const merged: PlatformApiConfig = {
    gatewayOrigin: supplied.gatewayOrigin ?? fallback.gatewayOrigin,
    authAuthority: supplied.authAuthority ?? fallback.authAuthority,
    authClientId: supplied.authClientId ?? fallback.authClientId,
    authScopes: supplied.authScopes ?? fallback.authScopes,
  };

  // The same checks a compiled configuration gets. A value that arrived over the wire deserves
  // them more, not less.
  assertConfigCarriesNoSecret(merged);
  return merged;
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
