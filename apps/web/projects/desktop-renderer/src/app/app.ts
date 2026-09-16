/**
 * The desktop renderer application shell.
 *
 * A shell, honestly scaffolded (constitution Principle IX): it establishes the layout, the routing
 * outlet and the one desktop-specific seam — the bridge — and implements no feature behaviour. The
 * customer journey itself comes from `customer-features` when plan Stage 3 composes it here; this
 * component adds only what the desktop surface needs beyond the shared UI.
 *
 * The host status it renders is diagnostic. Nothing on this screen is a permission, and nothing
 * here is gated on one: every authorization decision is the platform's, made server-side and
 * re-verified server-side (spec FR-SURF-004).
 */

import { Component, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { DesktopBridge } from './desktop/desktop-bridge';
import type { HostEndpoints, SessionBoundaryDescriptor } from './desktop/desktop-bridge.types';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  private readonly bridge = inject(DesktopBridge);

  /** Whether the renderer is running inside the desktop host. A rendering fact, not a permission. */
  protected readonly isDesktopHost = signal(this.bridge.isDesktopHost());

  protected readonly hostVersion = signal<string>('…');
  protected readonly hostPlatform = signal<string>('…');
  protected readonly endpoints = signal<HostEndpoints | null>(null);
  protected readonly sessionBoundary = signal<SessionBoundaryDescriptor | null>(null);

  public constructor() {
    void this.loadHostStatus();
  }

  /**
   * Read what the host reports.
   *
   * Failures are surfaced rather than swallowed: a bridge call that rejects means the host refused
   * the message, and rendering a blank value would hide that. No failure renders as an empty
   * result (spec FR-SURF-016).
   */
  private async loadHostStatus(): Promise<void> {
    try {
      const [version, platform, endpoints, boundary] = await Promise.all([
        this.bridge.getVersion(),
        this.bridge.getPlatform(),
        this.bridge.getEndpoints(),
        this.bridge.describeSessionBoundary(),
      ]);
      this.hostVersion.set(version.version);
      this.hostPlatform.set(platform.platform);
      this.endpoints.set(endpoints);
      this.sessionBoundary.set(boundary);
    } catch {
      this.hostVersion.set('unavailable');
      this.hostPlatform.set('unavailable');
    }
  }
}
