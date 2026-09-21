import type { PlatformApiConfig } from 'platform-core';

/**
 * Desktop renderer runtime configuration.
 *
 * No secret here, and none may be added (FE-SH-2, .claude/rules/22-web-typescript.md) — a
 * packaged desktop bundle is as
 * readable as a web page. One gateway origin and no second platform origin (spec FR-SURF-017); the
 * Electron main process narrows `connect-src` to this origin, SignalR and Entra, and the renderer
 * cannot weaken that policy.
 */
export const DESKTOP_RENDERER_CONFIG: PlatformApiConfig = {
  gatewayOrigin: 'https://localhost:7443',
  authAuthority: 'https://login.microsoftonline.com/common',
  authClientId: '00000000-0000-0000-0000-000000000000',
  authScopes: ['api://synthia-platform/.default'],
};
