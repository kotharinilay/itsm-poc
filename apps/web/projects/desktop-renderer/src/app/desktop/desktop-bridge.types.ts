/**
 * The renderer's view of the desktop `contextBridge` surface.
 *
 * ## Why this is declared here rather than imported
 *
 * `apps/web` and `apps/desktop` are separate deployables with separate toolchains and no build
 * dependency in either direction. Importing the host's types into the Angular workspace would
 * create exactly the coupling the repository is organised to prevent.
 *
 * So the renderer declares the shape it consumes, and the host proves the two agree:
 * `apps/desktop/tests/renderer-contract.spec.ts` reads this file and asserts that the members
 * declared here are exactly the members `BRIDGE_SURFACE` exposes. Drift fails the desktop suite.
 *
 * ## What this is not
 *
 * Nothing on this bridge carries authority. There is no member that reports a role, a tenant, a
 * permission or an approval state, and there must never be one: every such decision is made
 * server-side and re-verified server-side (FE-EL-1, .claude/rules/24-electron.md). The bridge
 * reports facts
 * about the host and the origins it was configured with — and nothing else.
 */

/** The running host application version. Informational. */
export interface HostVersion {
  readonly version: string;
}

/** The host platform identifier. Informational. */
export interface HostPlatform {
  readonly platform: string;
}

/**
 * The origins the host was configured with.
 *
 * Configuration, not authority: it says *where* to address the platform (spec FR-SURF-017 — a
 * single gateway), never what may be asked for once there.
 */
export interface HostEndpoints {
  readonly gatewayOrigin: string;
  readonly realtimeOrigin: string;
  readonly authorityOrigin: string;
}

/** Who holds a given responsibility on the desktop session path. */
export type SessionCustodian = 'renderer' | 'platform' | 'nobody';

/**
 * A description of the desktop session integration boundary.
 *
 * A shape, never a session. The renderer holds the credential; the platform holds the authority;
 * the main process holds neither and persists nothing.
 */
export interface SessionBoundaryDescriptor {
  readonly tokenCustody: SessionCustodian;
  readonly authorityHolder: SessionCustodian;
  readonly mainProcessPersistsSession: boolean;
  readonly hostResponsibilities: readonly string[];
}

/** The complete bridge surface. Every member is a zero-argument reader. */
export interface SynthiaDesktopApi {
  getVersion(): Promise<HostVersion>;
  getPlatform(): Promise<HostPlatform>;
  getEndpoints(): Promise<HostEndpoints>;
  describeSessionBoundary(): Promise<SessionBoundaryDescriptor>;
}

/** The global key the preload exposes the bridge under. */
export const BRIDGE_GLOBAL_KEY = 'synthiaDesktop';

declare global {
  interface Window {
    /**
     * Present only when running inside the desktop host. `undefined` in a browser, which is why
     * every consumer goes through `DesktopBridge` rather than touching this directly.
     */
    readonly synthiaDesktop?: SynthiaDesktopApi;
  }
}
