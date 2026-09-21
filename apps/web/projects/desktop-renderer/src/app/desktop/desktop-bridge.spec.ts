/**
 * Tests for the desktop bridge service.
 *
 * Two things are being proven. First, that the renderer degrades correctly when there is no host —
 * the same Angular code runs in a browser and must not throw there. Second, and more importantly,
 * that the service exposes **no authorization surface**: no method reports a role, a tenant, a
 * permission or an approval state, and `isDesktopHost()` is not repurposed as one
 * (FE-EL-1, .claude/rules/24-electron.md).
 */

import { TestBed } from '@angular/core/testing';

import { DesktopBridge, BROWSER_FALLBACK } from './desktop-bridge';
import { BRIDGE_GLOBAL_KEY, type SynthiaDesktopApi } from './desktop-bridge.types';

type Mutable = Record<string, unknown>;

function installBridge(api: unknown): void {
  (globalThis as Mutable)[BRIDGE_GLOBAL_KEY] = api;
}

function removeBridge(): void {
  delete (globalThis as Mutable)[BRIDGE_GLOBAL_KEY];
}

/** A complete stub host. Values are arbitrary; only the shape matters. */
function stubHost(): SynthiaDesktopApi {
  return {
    getVersion: () => Promise.resolve({ version: '1.2.3' }),
    getPlatform: () => Promise.resolve({ platform: 'win32' }),
    getEndpoints: () =>
      Promise.resolve({
        gatewayOrigin: 'https://gateway.example',
        realtimeOrigin: 'wss://realtime.example',
        authorityOrigin: 'https://login.microsoftonline.com',
      }),
    describeSessionBoundary: () =>
      Promise.resolve({
        tokenCustody: 'renderer' as const,
        authorityHolder: 'platform' as const,
        mainProcessPersistsSession: false,
        hostResponsibilities: ['Serve the renderer bundle from the application origin'],
      }),
  };
}

function create(): DesktopBridge {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({});
  return TestBed.inject(DesktopBridge);
}

describe('DesktopBridge', () => {
  afterEach(removeBridge);

  describe('in a browser, with no host', () => {
    beforeEach(removeBridge);

    it('reports that it is not running in the desktop host', () => {
      expect(create().isDesktopHost()).toBe(false);
    });

    it('falls back rather than throwing', async () => {
      const bridge = create();
      await expectAsync(bridge.getVersion()).toBeResolvedTo({
        version: BROWSER_FALLBACK.version,
      });
      await expectAsync(bridge.getPlatform()).toBeResolvedTo({
        platform: BROWSER_FALLBACK.platform,
      });
    });

    it('returns null for endpoints rather than guessing an origin', async () => {
      await expectAsync(create().getEndpoints()).toBeResolvedTo(null);
    });

    it('returns null for the session boundary', async () => {
      await expectAsync(create().describeSessionBoundary()).toBeResolvedTo(null);
    });
  });

  describe('inside the desktop host', () => {
    beforeEach(() => installBridge(stubHost()));

    it('reports that it is running in the desktop host', () => {
      expect(create().isDesktopHost()).toBe(true);
    });

    it('returns what the host reports', async () => {
      const bridge = create();
      await expectAsync(bridge.getVersion()).toBeResolvedTo({ version: '1.2.3' });
      await expectAsync(bridge.getPlatform()).toBeResolvedTo({ platform: 'win32' });
    });

    it('returns the configured origins, all of them HTTPS or WSS', async () => {
      const endpoints = await create().getEndpoints();
      expect(endpoints).not.toBeNull();
      expect(endpoints!.gatewayOrigin.startsWith('https://')).toBe(true);
      expect(endpoints!.realtimeOrigin.startsWith('wss://')).toBe(true);
      expect(endpoints!.authorityOrigin.startsWith('https://')).toBe(true);
    });

    it('describes a boundary in which the main process holds nothing', async () => {
      const boundary = await create().describeSessionBoundary();
      expect(boundary!.tokenCustody).toBe('renderer');
      expect(boundary!.authorityHolder).toBe('platform');
      expect(boundary!.mainProcessPersistsSession).toBe(false);
    });
  });

  describe('a malformed global is not treated as a bridge', () => {
    it('rejects a partially-initialised object', () => {
      installBridge({ getVersion: () => Promise.resolve({ version: 'x' }) });
      expect(create().isDesktopHost()).toBe(false);
    });

    it('rejects a non-object', () => {
      installBridge('not-a-bridge');
      expect(create().isDesktopHost()).toBe(false);
    });

    it('rejects null', () => {
      installBridge(null);
      expect(create().isDesktopHost()).toBe(false);
    });
  });

  describe('the bridge exposes no authorization surface', () => {
    beforeEach(() => installBridge(stubHost()));

    it('has no method whose name suggests a decision', () => {
      const bridge = create();
      const names = [
        ...Object.getOwnPropertyNames(Object.getPrototypeOf(bridge) as object),
        ...Object.getOwnPropertyNames(bridge),
      ];
      const forbidden = [
        'role',
        'permission',
        'approve',
        'approval',
        'tenant',
        'authoriz',
        'consent',
        'token',
        'signedin',
        'entitle',
      ];
      for (const name of names) {
        for (const word of forbidden) {
          expect(name.toLowerCase()).not.toContain(word);
        }
      }
    });

    it('never returns a field carrying identity, tenancy or a verdict', async () => {
      const boundary = await create().describeSessionBoundary();
      const endpoints = await create().getEndpoints();
      const forbidden = ['userId', 'tenantId', 'roles', 'token', 'isSignedIn', 'permitted'];
      for (const payload of [boundary, endpoints]) {
        for (const key of Object.keys(payload as object)) {
          expect(forbidden).not.toContain(key);
        }
      }
    });
  });
});
