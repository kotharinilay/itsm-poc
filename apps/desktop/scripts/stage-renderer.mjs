/**
 * Stage the built Angular `desktop-renderer` bundle into the desktop package.
 *
 * The two workspaces have no build dependency on each other — this script copies an *artifact*,
 * which is a packaging step, not a code dependency. The desktop package never imports from
 * `apps/web`, and `apps/web` never knows the host exists.
 *
 * The bundle lands at `dist/renderer/`, which is where `main/index.js` resolves `BUNDLE_ROOT` and
 * where the `app://renderer` protocol handler serves from.
 *
 * Fails loudly when the bundle is missing. A host that starts with no renderer shows an empty
 * window, and an empty window is a much harder thing to diagnose than a failed build.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const DESKTOP_ROOT = path.resolve(here, '..');

/** Angular's `@angular/build:application` output for the `desktop-renderer` project. */
const SOURCE = path.resolve(DESKTOP_ROOT, '..', 'web', 'dist', 'desktop-renderer', 'browser');
const DESTINATION = path.resolve(DESKTOP_ROOT, 'dist', 'renderer');

if (!fs.existsSync(SOURCE)) {
  console.error(
    `Renderer bundle not found at ${SOURCE}.\n` +
      'Build it first:  cd apps/web && npm run build -- desktop-renderer',
  );
  process.exit(1);
}

if (!fs.existsSync(path.join(SOURCE, 'index.html'))) {
  console.error(`Renderer bundle at ${SOURCE} has no index.html — the build did not complete.`);
  process.exit(1);
}

// Replace rather than merge, so a file removed from the Angular build does not survive in the
// staged copy and keep getting served.
fs.rmSync(DESTINATION, { recursive: true, force: true });
fs.mkdirSync(path.dirname(DESTINATION), { recursive: true });
fs.cpSync(SOURCE, DESTINATION, { recursive: true });

console.log(`Staged renderer bundle: ${SOURCE} -> ${DESTINATION}`);
