import { Injectable, signal } from '@angular/core';

/**
 * The renderer's view of the Electron `contextBridge` surface.
 *
 * ## The only thing this application adds
 *
 * The desktop renderer reuses `customer-features` wholesale and contributes this service and
 * nothing else (plan Stage 3). Anything else it grew would be a second copy of a customer feature,
 * drifting from the portal's.
 *
 * ## It decides nothing
 *
 * No business authorization decision exists in the renderer **or** the main process (FE-EL-1,
 * .claude/rules/24-electron.md). This service asks the host to do host things — run a verified instruction, report
 * what happened. Whether that instruction was ever authorized was decided by the platform, is
 * carried by the instruction fetched over the Customer API, and is verified by content hash before
 * anything runs (ADR-0004).
 *
 * ## It is typed, narrow, and optional
 *
 * `window.synthia` is present only inside the Electron host; in a browser it is absent, and
 * `isAvailable` is how a shared feature can tell. The preload exposes this narrow surface and never
 * raw `ipcRenderer` or a broad Electron or Node API.
 */
export interface DesktopBridge {
  readonly platform: 'windows' | 'macos' | 'linux';
  readonly hostVersion: string;

  /**
   * Execute an instruction already fetched and verified against the Customer API.
   *
   * The instruction is passed by identifier and content hash. The bridge is not a channel for
   * script content, and the host re-verifies before running.
   */
  executeVerifiedInstruction(request: {
    readonly workItemId: string;
    readonly contentHash: string;
  }): Promise<{
    readonly exitStatus: 'succeeded' | 'failed' | 'aborted';
    readonly summary: string;
  }>;
}

declare global {
  interface Window {
    readonly synthia?: DesktopBridge;
  }
}

@Injectable({ providedIn: 'root' })
export class DesktopBridgeService {
  private readonly bridge: DesktopBridge | undefined =
    typeof window === 'undefined' ? undefined : window.synthia;

  private readonly availableSignal = signal(this.bridge !== undefined);

  /** False in a browser and in tests. A feature branches on this rather than sniffing the agent. */
  readonly isAvailable = this.availableSignal.asReadonly();

  platform(): DesktopBridge['platform'] | null {
    return this.bridge?.platform ?? null;
  }

  hostVersion(): string | null {
    return this.bridge?.hostVersion ?? null;
  }

  /**
   * Run a verified instruction through the host.
   *
   * Rejects rather than silently no-opping when the host is absent: a caller that reached here in a
   * browser has a bug, and pretending the work ran would be worse than failing.
   */
  async executeVerifiedInstruction(request: {
    readonly workItemId: string;
    readonly contentHash: string;
  }): Promise<{
    readonly exitStatus: 'succeeded' | 'failed' | 'aborted';
    readonly summary: string;
  }> {
    if (this.bridge === undefined) {
      throw new Error('The desktop host bridge is not available in this environment.');
    }
    return this.bridge.executeVerifiedInstruction(request);
  }
}
