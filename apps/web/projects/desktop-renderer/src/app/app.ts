import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { SkipLink } from 'design-system';
import { AuthService } from 'platform-core';
import { DesktopBridgeService } from './desktop-bridge.service';

/**
 * Desktop renderer shell (spec FR-SURF-001 — the customer desktop application).
 *
 * Reuses `customer-features` and adds only the desktop bridge (plan Stage 3).
 *
 * Like the customer portal, every person here is an end user: no staff role check is applied on a
 * customer surface and holding a staff role confers nothing (spec FR-SURF-008). And like the
 * portal, this shell decides nothing — no business authorization decision exists in the renderer
 * or in the main process (constitution Principle VII).
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
  protected readonly desktop = inject(DesktopBridgeService);
}
