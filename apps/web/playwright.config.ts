import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end configuration for the Stage 3 accessibility gate.
 *
 * Each surface is served on its own port so the sweep covers all three in one run — the staff
 * portal is held to the same standard as the customer surfaces (spec FR-SURF-010).
 *
 * Browsers are not installed by `npm ci`. Run `npx playwright install chromium` once before
 * `npm run e2e`.
 */
export default defineConfig({
  testDir: './e2e',
  // The CSP hosting check runs against the BUILT portals behind the reference host, not against
  // `ng serve` — it has its own configuration (playwright.csp.config.ts).
  testIgnore: ['csp-hosting.spec.ts'],
  fullyParallel: true,
  reporter: process.env['CI'] === undefined ? 'list' : 'github',
  use: { ...devices['Desktop Chrome'] },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'npx ng serve customer-portal --port 4200',
      port: 4200,
      reuseExistingServer: process.env['CI'] === undefined,
      timeout: 180_000,
    },
    {
      command: 'npx ng serve staff-portal --port 4201',
      port: 4201,
      reuseExistingServer: process.env['CI'] === undefined,
      timeout: 180_000,
    },
    {
      command: 'npx ng serve desktop-renderer --port 4202',
      port: 4202,
      reuseExistingServer: process.env['CI'] === undefined,
      timeout: 180_000,
    },
  ],
});
