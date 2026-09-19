import { defineConfig, devices } from '@playwright/test';

/**
 * The CSP baseline, SENT and OBEYED — the built portals behind the reference hosting tier.
 *
 * `ng serve` cannot deliver the policy: it needs a fresh nonce per response, and the dev server
 * only sends static headers. So this runs the production build through `scripts/csp-host.mjs`,
 * which does what a production host must, and `e2e/csp-hosting.spec.ts` fails on any violation.
 *
 * Requires `npm run build` first; `npm run test:csp` does both.
 */
const HOST = 'node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/csp-host.mjs';

export default defineConfig({
  testDir: './e2e',
  testMatch: ['csp-hosting.spec.ts'],
  fullyParallel: true,
  reporter: process.env['CI'] === undefined ? 'list' : 'github',
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${HOST} customer-portal 4300`,
      port: 4300,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `${HOST} staff-portal 4301`,
      port: 4301,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
