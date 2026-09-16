import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FocusTrap } from 'design-system';
import { CustomerApiClient } from 'platform-core';

/**
 * Consent prompt shell.
 *
 * Structural shell only — no consent behaviour is implemented.
 *
 * Two rules are built into the shape rather than left to the implementer:
 *
 *  - **Consent is recorded by calling the consent endpoint, and by nothing else.** An affirmative
 *    chat message is never consent (contracts/customer-api.md), so there is no path from the chat
 *    surface into this one that records anything.
 *  - **It is operable by keyboard alone** (spec FR-SURF-012). The dialog traps focus and restores
 *    it on close, which is why `FocusTrap` is here in the shell and not deferred to the feature.
 */
@Component({
  selector: 'cf-consent-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FocusTrap],
  templateUrl: './consent-shell.html',
  styleUrl: './consent-shell.css',
})
export class ConsentShell {
  protected readonly api = inject(CustomerApiClient);
  protected readonly open = signal(false);
}
