import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { SkipLink } from 'design-system';
import { AuthService } from 'platform-core';

/**
 * Customer portal shell (spec FR-SURF-001).
 *
 * Composed from `customer-features` and `platform-core` and holding no feature logic of its own.
 *
 * Every person here is an **end user**, including a Synoptek staff member. No staff role check is
 * applied on this surface and holding a staff role confers nothing (spec FR-SURF-008) — which is
 * why there is no role gating anywhere in this application, and why `AuthService` is used only to
 * show who is signed in.
 */
@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, SkipLink],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly auth = inject(AuthService);
}
