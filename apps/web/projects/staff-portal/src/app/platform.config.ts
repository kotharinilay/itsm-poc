import type { PlatformApiConfig } from 'platform-core';

/**
 * Staff portal runtime configuration.
 *
 * No secret here, and none may be added (constitution §Secrets). One gateway origin and no second
 * platform origin (spec FR-SURF-017). Deployed values come from the hosting tier.
 */
export const STAFF_PORTAL_CONFIG: PlatformApiConfig = {
  gatewayOrigin: 'https://localhost:7443',
  authAuthority: 'https://login.microsoftonline.com/common',
  authClientId: '00000000-0000-0000-0000-000000000000',
  authScopes: ['api://synthia-platform/.default'],
};
