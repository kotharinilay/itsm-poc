import { DOCUMENT, inject } from '@angular/core';
import { assertNoCspMetaTag } from './content-security-policy';

/**
 * The workspace sanitization policy, written down where it can be cited in review.
 *
 * ## Angular's sanitizer is left on
 *
 * Interpolation escapes, `[innerHTML]` is sanitized, and `[href]`/`[src]` are checked for unsafe
 * schemes. That is the default, and the default is correct. Nothing in this workspace turns it off.
 *
 * ## `bypassSecurityTrust*` is absent
 *
 * `DomSanitizer.bypassSecurityTrustHtml` and its siblings hand the value straight to the DOM. Every
 * one of them is a deliberate hole, and each is a standing invitation to XSS the next time the
 * value's origin changes. FE-NG-10 (.claude/rules/23-angular.md): they are absent from this
 * scaffold.
 *
 * This is enforced in three places rather than asserted once:
 *  - ESLint `no-restricted-properties` fails the build on a call (`eslint.config.js`);
 *  - `no-authz.spec.ts` scans the source of every project for the identifier;
 *  - `security.spec.ts` asserts the CSP baseline that would blunt an injection that got through.
 *
 * Needing one is a design problem — render the value as text, or model the markup as data and build
 * it from components. If a case genuinely survives that, it takes an ADR, not a code comment.
 *
 * ## Agent-authored content
 *
 * Streamed model output is untrusted by construction. It is rendered as **text**, never as HTML. A
 * future markdown renderer parses to a component tree; it never produces an HTML string for
 * `[innerHTML]`.
 */
export const SANITIZATION_POLICY = {
  bypassApisPermitted: false,
  agentContentRendersAs: 'text',
  cspDeliveredAs: 'response-header',
} as const;

/**
 * Bootstrap-time browser security check.
 *
 * Runs at application start so a surface that has lost its CSP header, or gained a `<meta>` policy,
 * fails visibly in development instead of silently in production.
 */
export function verifyBrowserSecurityBaseline(): void {
  assertNoCspMetaTag(inject(DOCUMENT));
}
