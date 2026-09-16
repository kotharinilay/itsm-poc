import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

/**
 * Accessibility sweep across all three surfaces.
 *
 * Spec FR-SURF-010 and SC-SURF-002: all three client surfaces conform to WCAG 2.2 Level AA. **The
 * staff portal is held to the same level as the customer surfaces; there is no best-effort
 * surface** — which is why the three are swept by the same loop with the same rule set rather than
 * by three checks somebody could tune independently.
 *
 * The Stage 3 gate is zero Level A/AA failures on the scaffolded journeys.
 *
 * ## What this sweep does and does not reach, today
 *
 * No identity plane is wired in Stage 3, so nobody is signed in when these run. On the staff
 * portal the presentation guards therefore deny, and `/queue` renders the application shell with an
 * empty outlet rather than the queue itself — so for that surface this sweep covers the shell,
 * the navigation and the landmarks, and not yet the feature content behind the gate.
 *
 * That is stated rather than worked around: signing in a fake technician here would make the sweep
 * look broader than it is. The staff feature shells are covered meanwhile by their component specs,
 * and this sweep reaches them as soon as Stage 5 makes a real session possible.
 */

interface Surface {
  readonly name: string;
  readonly port: number;
  readonly routes: readonly string[];
}

const SURFACES: readonly Surface[] = [
  { name: 'customer-portal', port: 4200, routes: ['/sessions'] },
  { name: 'staff-portal', port: 4201, routes: ['/queue'] },
  { name: 'desktop-renderer', port: 4202, routes: ['/sessions'] },
];

/** WCAG 2.2, Levels A and AA. Nothing below AA is asserted; nothing at AA is skipped. */
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

for (const surface of SURFACES) {
  test.describe(surface.name, () => {
    for (const route of surface.routes) {
      test(`${route} has no Level A or AA violation`, async ({ page }) => {
        await page.goto(`http://localhost:${surface.port}${route}`);
        await page.waitForLoadState('networkidle');

        const results = await new AxeBuilder({ page }).withTags(WCAG_AA_TAGS).analyze();

        // Report every violation, not just the first — a failure should say what to fix.
        expect(results.violations.map((violation) => `${violation.id}: ${violation.help}`)).toEqual(
          [],
        );
      });

      test(`${route} exposes a skip link as the first tab stop`, async ({ page }) => {
        await page.goto(`http://localhost:${surface.port}${route}`);
        await page.keyboard.press('Tab');
        const focused = page.locator(':focus');
        await expect(focused).toHaveAttribute('href', '#main-content');
      });
    }
  });
}
