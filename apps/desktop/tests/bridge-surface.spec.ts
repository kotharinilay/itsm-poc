/**
 * The bridge is narrow — and stays narrow.
 *
 * "Raw `ipcRenderer` is never exposed" and "the bridge is narrow" are claims that decay silently:
 * nothing breaks when a member is added, so nothing catches it. This suite makes both claims
 * testable, by asserting the preload's exposed surface against the contract rather than against a
 * reviewer's memory.
 *
 * The preload cannot be imported here — it calls `contextBridge.exposeInMainWorld` at module scope
 * and needs a real Electron preload context. So the assertions are made against its **source**,
 * which is also where the failure would be introduced.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  ARGUMENT_VALIDATORS,
  BRIDGE_GLOBAL_KEY,
  BRIDGE_SURFACE,
  IPC_CHANNELS,
  areArgumentsValid,
  isIpcChannel,
} from '../src/ipc-contracts/index.js';
import { buildHandlers, contractBridgeMembers, contractChannels, handledChannels } from '../src/main/app-shell.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const PRELOAD_SOURCE = fs.readFileSync(
  path.resolve(here, '..', 'src', 'preload', 'bridge.ts'),
  'utf8',
);

/**
 * The preload with comments and import declarations stripped.
 *
 * Comments go because the file *documents* the `ipcRenderer` rule at length, and a guard that
 * flags its own documentation is a guard somebody disables. Imports go because importing
 * `ipcRenderer` into the preload's module scope is exactly right — capturing it in a closure is
 * how it stays unreachable. What these patterns look for is `ipcRenderer` crossing the bridge,
 * which can only happen in the exposed object.
 */
const PRELOAD_CODE = PRELOAD_SOURCE.replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/\/\/.*$/gm, ' ')
  .replace(/^import\s[\s\S]*?from\s+'[^']*';$/gm, ' ');

describe('the contract and the handler table agree', () => {
  const handlers = buildHandlers(
    { version: '0.1.0', platform: 'win32' },
    {
      gatewayOrigin: 'https://gateway.example',
      realtimeOrigin: 'wss://realtime.example',
      authorityOrigin: 'https://login.microsoftonline.com',
    },
  );

  it('registers a handler for every declared channel, and no others', () => {
    expect(handledChannels(handlers)).toEqual(contractChannels());
  });

  it('declares an argument validator for every channel', () => {
    expect(Object.keys(ARGUMENT_VALIDATORS).sort()).toEqual(contractChannels());
  });

  it('maps every bridge member to a declared channel', () => {
    for (const channel of Object.values(BRIDGE_SURFACE)) {
      expect(isIpcChannel(channel)).toBe(true);
    }
  });

  it('exposes a bridge member for every channel — no channel is reachable only from inside', () => {
    expect(Object.values(BRIDGE_SURFACE).sort()).toEqual([...IPC_CHANNELS].sort());
  });

  it('rejects arguments on every channel, since every channel takes none', () => {
    for (const channel of IPC_CHANNELS) {
      expect(areArgumentsValid(channel, [])).toBe(true);
      expect(areArgumentsValid(channel, [undefined])).toBe(false);
      expect(areArgumentsValid(channel, [{ nested: { deep: true } }])).toBe(false);
    }
  });
});

describe('the preload never exposes raw ipcRenderer or a broad API', () => {
  it('exposes exactly one global, under the contract key', () => {
    const exposures = PRELOAD_CODE.match(/exposeInMainWorld\s*\(/g) ?? [];
    expect(exposures).toHaveLength(1);
    expect(PRELOAD_CODE).toContain('exposeInMainWorld(BRIDGE_GLOBAL_KEY');
    expect(BRIDGE_GLOBAL_KEY).toBe('synthiaDesktop');
  });

  it.each([
    [/exposeInMainWorld\s*\([^,]+,\s*ipcRenderer\s*\)/, 'ipcRenderer itself'],
    [/ipcRenderer\s*[,}]/, 'ipcRenderer as an object member'],
    [/\.\.\.\s*ipcRenderer/, 'ipcRenderer spread into the surface'],
    [/ipcRenderer\.on\b/, 'an unfiltered event listener'],
    [/ipcRenderer\.send(?:Sync)?\b/, 'a fire-and-forget send'],
    [/ipcRenderer\.postMessage\b/, 'a raw message port'],
    [/require\s*\(/, 'a CommonJS require the renderer could reach'],
    [/process\s*[,}]/, 'the process object'],
    [/exposeInMainWorld\s*\([^,]+,\s*\{[^}]*shell/, 'the shell module'],
  ])('does not expose %s (%s)', (pattern) => {
    expect(pattern.test(PRELOAD_CODE)).toBe(false);
  });

  it('uses ipcRenderer.invoke only, and only with a contract channel', () => {
    const invocations = PRELOAD_CODE.match(/ipcRenderer\.\w+/g) ?? [];
    expect([...new Set(invocations)]).toEqual(['ipcRenderer.invoke']);
    // The single call site takes the `channel` parameter, never a caller-supplied string.
    expect(PRELOAD_CODE).toContain('ipcRenderer.invoke(channel)');
  });

  it('exposes exactly the members the contract declares', () => {
    // Each member appears as `name: (` in the exposed object literal.
    const declared = [...PRELOAD_CODE.matchAll(/^\s{2}(\w+):\s*\(/gm)].map((m) => m[1] as string);
    expect(declared.sort()).toEqual(contractBridgeMembers());
  });

  it('passes no argument through to the main process from any member', () => {
    // Every member is a zero-parameter arrow: `name: (): Promise<...> =>`.
    const members = [...PRELOAD_CODE.matchAll(/^\s{2}\w+:\s*\(([^)]*)\)/gm)].map(
      (m) => (m[1] ?? '').trim(),
    );
    expect(members.length).toBeGreaterThan(0);
    for (const parameters of members) {
      expect(parameters).toBe('');
    }
  });
});

describe('the preload is built so a sandboxed renderer can load it', () => {
  /**
   * `sandbox: true` is unconditional (plan Stage 4), and a sandboxed preload is loaded by
   * Electron's own CommonJS loader rather than Node's. That imposes two constraints that nothing
   * else in the build enforces:
   *
   *  - it **cannot be ESM**, and this package is `"type": "module"`, so `tsc` output would be;
   *  - its `require` is a polyfill resolving only a short list of built-ins, never a relative
   *    file — so every import except `electron` must be bundled in.
   *
   * Breaking either produces a preload that fails to load at runtime, leaving `window.synthiaDesktop`
   * undefined and the bridge silently absent. Nothing else catches that before a user does, so the
   * build configuration is asserted here.
   */
  const packageJson = JSON.parse(
    fs.readFileSync(path.resolve(here, '..', 'package.json'), 'utf8'),
  ) as { scripts: Record<string, string> };

  const buildPreload = packageJson.scripts['build:preload'] ?? '';

  it('bundles the preload rather than emitting a module graph', () => {
    expect(buildPreload).toContain('--bundle');
  });

  it('emits CommonJS, because a sandboxed preload cannot be ESM', () => {
    expect(buildPreload).toContain('--format=cjs');
  });

  it('leaves only electron external — everything else must be bundled in', () => {
    const externals = [...buildPreload.matchAll(/--external:(\S+)/g)].map((m) => m[1]);
    expect(externals).toEqual(['electron']);
  });

  it('is excluded from the tsc emit, so the esbuild output is not overwritten', () => {
    const tsconfig = fs.readFileSync(path.resolve(here, '..', 'tsconfig.json'), 'utf8');
    expect(tsconfig).toContain('"src/preload"');
  });

  it('is still type-checked, by its own config', () => {
    expect(packageJson.scripts['typecheck']).toContain('tsconfig.preload.json');
  });
});
