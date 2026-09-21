/**
 * The desktop bridge service — the renderer's only route to the host.
 *
 * Plan Stage 3 composes `desktop-renderer` from the shared customer UI "adding only the desktop
 * bridge service". This is that service, and it is the *only* place in the Angular workspace that
 * touches `window.synthiaDesktop`. Everything else injects this.
 *
 * Two reasons it is a service rather than a direct global read:
 *
 *  1. **The bridge may be absent.** The same Angular code runs in a browser during development and
 *     in tests, where there is no host. Every method degrades to a stated fallback rather than
 *     throwing on a missing global.
 *  2. **It is a seam.** One injectable means one place to assert against, one place to mock, and
 *     one place a reviewer looks when asking what the renderer can ask the host for.
 *
 * This service makes no authorization decision and exposes nothing that could be mistaken for one.
 * `isDesktopHost()` answers "am I running in Electron", which is a rendering question — never
 * "may this user do that", which is the platform's and is re-decided server-side (FE-EL-1,
 * .claude/rules/24-electron.md).
 */

import { Injectable } from '@angular/core';

import {
  BRIDGE_GLOBAL_KEY,
  type HostEndpoints,
  type HostPlatform,
  type HostVersion,
  type SessionBoundaryDescriptor,
  type SynthiaDesktopApi,
} from './desktop-bridge.types';

/** What the renderer reports when there is no host to ask. */
export const BROWSER_FALLBACK = Object.freeze({
  version: 'browser',
  platform: 'browser',
});

@Injectable({ providedIn: 'root' })
export class DesktopBridge {
  /**
   * The bridge, or `null` in a browser.
   *
   * Read once at construction. Re-reading per call would let a later script replace the global
   * and have this service follow it; the preload has already run by the time Angular bootstraps,
   * so one read at construction is both sufficient and the narrower window.
   */
  private readonly api: SynthiaDesktopApi | null;

  public constructor() {
    const candidate = (globalThis as { [BRIDGE_GLOBAL_KEY]?: unknown })[BRIDGE_GLOBAL_KEY];
    this.api = isBridge(candidate) ? candidate : null;
  }

  /** Whether the renderer is running inside the desktop host. A rendering fact, not a permission. */
  public isDesktopHost(): boolean {
    return this.api !== null;
  }

  /** The host version, or `'browser'` outside the host. */
  public async getVersion(): Promise<HostVersion> {
    return this.api === null ? { version: BROWSER_FALLBACK.version } : await this.api.getVersion();
  }

  /** The host platform, or `'browser'` outside the host. */
  public async getPlatform(): Promise<HostPlatform> {
    return this.api === null
      ? { platform: BROWSER_FALLBACK.platform }
      : await this.api.getPlatform();
  }

  /**
   * The origins the host was configured with, or `null` in a browser.
   *
   * `null` rather than a guessed default: in a browser the app is served *from* the platform and
   * uses relative URLs, so there is nothing to substitute and pretending otherwise would hide a
   * misconfiguration behind a plausible-looking value.
   */
  public async getEndpoints(): Promise<HostEndpoints | null> {
    return this.api === null ? null : await this.api.getEndpoints();
  }

  /** The session boundary descriptor, or `null` in a browser. */
  public async describeSessionBoundary(): Promise<SessionBoundaryDescriptor | null> {
    return this.api === null ? null : await this.api.describeSessionBoundary();
  }
}

/**
 * Structural check on the global before it is trusted as the bridge.
 *
 * The preload is the only thing that can set this global under `contextIsolation`, so this is not
 * a security boundary — it is a correctness one. It keeps a stale or partially-initialised global
 * from producing a `TypeError` deep inside a component, which is a much worse failure than
 * falling back to browser mode.
 */
function isBridge(candidate: unknown): candidate is SynthiaDesktopApi {
  if (typeof candidate !== 'object' || candidate === null) {
    return false;
  }
  const members: readonly (keyof SynthiaDesktopApi)[] = [
    'getVersion',
    'getPlatform',
    'getEndpoints',
    'describeSessionBoundary',
  ];
  return members.every(
    (member) => typeof (candidate as Record<string, unknown>)[member] === 'function',
  );
}
