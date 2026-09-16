import type { PlatformApiConfig } from 'platform-core';

/**
 * Customer portal runtime configuration.
 *
 * **Nothing here is a secret, and nothing here may become one** (constitution §Secrets). Every
 * value is a public origin or a public identifier. A browser cannot keep a credential: anything
 * shipped to the page is readable by whoever loads the page. Tokens are acquired at runtime through
 * the auth integration and are never baked into a build.
 *
 * One `gatewayOrigin` and no second platform origin — spec FR-SURF-017. Which backend serves a
 * given operation is not this application's concern.
 *
 * In a deployed environment these values are supplied by the hosting tier (a fetched config
 * document or build-time substitution). The development defaults below point at a local gateway.
 */
export const CUSTOMER_PORTAL_CONFIG: PlatformApiConfig = {
  gatewayOrigin: 'https://localhost:7443',
  authAuthority: 'https://login.microsoftonline.com/common',
  authClientId: '00000000-0000-0000-0000-000000000000',
  authScopes: ['api://synthia-platform/.default'],
};
