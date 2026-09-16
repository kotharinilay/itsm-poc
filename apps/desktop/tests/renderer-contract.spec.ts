/**
 * The host and the renderer agree on the bridge.
 *
 * `apps/web` and `apps/desktop` are separate deployables with no build dependency in either
 * direction, so the renderer cannot import the host's types — it declares the shape it consumes in
 * `desktop-bridge.types.ts`. Two hand-maintained declarations of one contract drift, and the drift
 * is invisible until runtime: the renderer calls a member the host stopped exposing, and the call
 * rejects on a user's machine.
 *
 * This suite is what makes the drift visible at build time instead. It reads the renderer's
 * declaration as **text** — no import, no compilation coupling, no dependency — and asserts the
 * two agree.
 *
 * If the renderer file has moved, this fails. That is intentional: a guard that skips when it
 * cannot find its subject is a guard that silently stops guarding.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { BRIDGE_GLOBAL_KEY, BRIDGE_SURFACE } from '../src/ipc-contracts/index.js';

const here = path.dirname(fileURLToPath(import.meta.url));

const RENDERER_TYPES = path.resolve(
  here,
  '..',
  '..',
  'web',
  'projects',
  'desktop-renderer',
  'src',
  'app',
  'desktop',
  'desktop-bridge.types.ts',
);

describe('the renderer declares the same bridge the host exposes', () => {
  it('finds the renderer declaration where it is expected', () => {
    expect(
      fs.existsSync(RENDERER_TYPES),
      `Expected the renderer bridge declaration at ${RENDERER_TYPES}. If it moved, update this ` +
        'path — do not delete the assertion.',
    ).toBe(true);
  });

  const source = fs.existsSync(RENDERER_TYPES) ? fs.readFileSync(RENDERER_TYPES, 'utf8') : '';

  it('declares exactly the members the host exposes, and no others', () => {
    // The members of `interface SynthiaDesktopApi { ... }`, each declared as `name(): Promise<…>`.
    const body = /interface\s+SynthiaDesktopApi\s*\{([\s\S]*?)\n\}/.exec(source)?.[1] ?? '';
    const declared = [...body.matchAll(/^\s*(\w+)\s*\(/gm)].map((m) => m[1] as string).sort();

    expect(declared).toEqual(Object.keys(BRIDGE_SURFACE).sort());
  });

  it('uses the same global key', () => {
    expect(source).toContain(`export const BRIDGE_GLOBAL_KEY = '${BRIDGE_GLOBAL_KEY}'`);
  });

  it('declares the global as optional, so the renderer handles running in a browser', () => {
    expect(/readonly\s+synthiaDesktop\?\s*:/.test(source)).toBe(true);
  });

  it('declares no member carrying authority', () => {
    const body = /interface\s+SynthiaDesktopApi\s*\{([\s\S]*?)\n\}/.exec(source)?.[1] ?? '';
    for (const word of ['role', 'permission', 'approve', 'tenant', 'authoriz', 'token']) {
      expect(body.toLowerCase()).not.toContain(word);
    }
  });
});
