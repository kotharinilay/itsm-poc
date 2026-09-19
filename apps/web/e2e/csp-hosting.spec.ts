import { expect, test, type Page } from '@playwright/test';

import {
  FORBIDDEN_CSP_TOKENS,
  REQUIRED_CSP_DIRECTIVES,
} from '../projects/platform-core/src/lib/security/content-security-policy';

/**
 * The Stage 3 CSP baseline is delivered as a response header, and the built portals run under it.
 *
 * Until this existed the policy was built and unit-tested but never SENT: no hosting tier in the
 * repository set the header, so nothing had ever shown that the portals work under it. These
 * tests drive the production build through `scripts/csp-host.mjs` — the same server the portal
 * image runs (ADR-0009) — and fail on any violation the browser reports.
 */

interface Surface {
  readonly name: string;
  readonly port: number;
  readonly route: string;
}

const SURFACES: readonly Surface[] = [
  { name: 'customer-portal', port: 4300, route: '/sessions' },
  { name: 'staff-portal', port: 4301, route: '/queue' },
];

/** Collect every CSP violation the page reports, from the first byte of the document. */
async function recordViolations(page: Page): Promise<string[]> {
  const violations: string[] = [];
  await page.exposeFunction('__reportCspViolation', (description: string) => {
    violations.push(description);
  });
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => {
      const report = (window as unknown as { __reportCspViolation: (d: string) => void })
        .__reportCspViolation;
      report(`${event.violatedDirective} blocked ${event.blockedURI || '(inline)'}`);
    });
  });
  return violations;
}

for (const surface of SURFACES) {
  test.describe(surface.name, () => {
    const url = `http://127.0.0.1:${surface.port}${surface.route}`;

    test('the policy arrives as a response header, complete and without a weakening token', async ({
      request,
    }) => {
      const response = await request.get(url);
      const policy = response.headers()['content-security-policy'] ?? '';

      for (const directive of REQUIRED_CSP_DIRECTIVES) {
        expect(policy, `missing ${directive}`).toContain(directive);
      }
      for (const token of FORBIDDEN_CSP_TOKENS) {
        expect(policy).not.toContain(`'${token}'`);
      }
      expect(policy).not.toMatch(/(^|\s)\*(\s|;|$)/);
    });

    test('every document response carries a fresh nonce, handed to Angular', async ({
      request,
    }) => {
      const nonceOf = async (): Promise<{ header: string; attribute: string }> => {
        const response = await request.get(url);
        const header = /'nonce-([^']+)'/.exec(response.headers()['content-security-policy'] ?? '');
        const attribute = /ngCspNonce="([^"]+)"/.exec(await response.text());
        return { header: header?.[1] ?? '', attribute: attribute?.[1] ?? '' };
      };

      const first = await nonceOf();
      const second = await nonceOf();

      expect(first.header).not.toBe('');
      expect(first.attribute).toBe(first.header);
      expect(second.header).not.toBe(first.header);
    });

    test('the document carries the environment the hosting tier supplied', async ({ request }) => {
      // An image promoted by digest cannot carry its own environment (ADR-0009). The tier writes
      // it in; `readHostedConfig` reads it back. A block that stopped arriving would leave a
      // deployed portal pointing at the compiled development default — silently.
      const body = await (await request.get(url)).text();
      const block =
        /<script type="application\/json" id="synthia-platform-config">(.*?)<\/script>/.exec(body);

      expect(block, 'the document carries no platform config block').not.toBeNull();

      const config = JSON.parse(block?.[1] ?? '{}') as Record<string, string>;
      expect(config['gatewayOrigin']).toBe('https://api.synthia.example');
      expect(config['authClientId']).toBe('11111111-1111-1111-1111-111111111111');

      // It is a data block, not a script: nothing in it executes, so it needs no nonce.
      expect(body).not.toContain('<script>');
    });

    test('the portal renders under the policy with no violation', async ({ page }) => {
      const violations = await recordViolations(page);

      await page.goto(url);
      await page.waitForLoadState('networkidle');

      await expect(page.locator('a[href="#main-content"]')).toHaveCount(1);
      expect(violations).toEqual([]);
    });
  });
}
