// The reference hosting tier for the two browser portals: what a production host MUST do, runnable.
//
// The CSP baseline is a RESPONSE HEADER with a PER-RESPONSE style nonce (platform-core
// content-security-policy.ts). A static header cannot satisfy that — a fixed nonce is no nonce — so
// `ng serve` cannot deliver it, and nothing else in the repository did: the policy was built and
// unit-tested but never sent. This server is the executable statement of the hosting contract:
//
//   1. a fresh nonce per document response,
//   2. the same nonce handed to Angular through `ngCspNonce` on the root element,
//   3. the header produced by `buildCspHeader` itself — imported, never restated — so the policy
//      that is tested is the policy that is served.
//
// The production hosting tier is not yet defined anywhere in `build/infra/` (tracked as an open task
// in specs/001-platform-scaffold/tasks.md). Whatever it becomes must do these three things;
// `e2e/csp-hosting.spec.ts` drives the built portals through this server and fails on any CSP
// violation.
//
// Usage:  node scripts/csp-host.mjs <customer-portal|staff-portal> <port>
// Needs Node 22.18+ (TypeScript type stripping, to import the policy source directly) and a built
// portal in dist/ (`npm run build`).

import { randomBytes } from 'node:crypto';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildCspHeader } from '../projects/platform-core/src/lib/security/content-security-policy.ts';

const PORTALS = new Set(['customer-portal', 'staff-portal']);
const [app, portArgument] = process.argv.slice(2);

if (!PORTALS.has(app ?? '') || !portArgument) {
  console.error('Usage: node scripts/csp-host.mjs <customer-portal|staff-portal> <port>');
  process.exit(2);
}

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '..', 'dist', app, 'browser');

// The origins the portal may reach. Local defaults; a real host supplies its own.
const origins = {
  gatewayOrigin: process.env.SYNTHIA_GATEWAY_ORIGIN ?? 'https://api.synthia.local',
  signalROrigin: process.env.SYNTHIA_SIGNALR_ORIGIN ?? 'wss://realtime.synthia.local',
  authAuthority: process.env.SYNTHIA_AUTH_AUTHORITY ?? 'https://login.microsoftonline.com',
};

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.ico': 'image/x-icon',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
};

/** Resolve a request path inside the build output, or null when it would leave it. */
function contained(urlPath) {
  const candidate = resolve(root, '.' + normalize(decodeURIComponent(urlPath)));
  return candidate === root || candidate.startsWith(root + sep) ? candidate : null;
}

async function document(response) {
  const nonce = randomBytes(16).toString('base64');
  const html = (await readFile(join(root, 'index.html'), 'utf8')).replace(
    '<app-root>',
    `<app-root ngCspNonce="${nonce}">`,
  );
  response.writeHead(200, {
    'Content-Type': TYPES['.html'],
    'Content-Security-Policy': buildCspHeader(origins, { styleNonce: nonce }),
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-store',
  });
  response.end(html);
}

const server = createServer(async (request, response) => {
  const path = new URL(request.url ?? '/', 'http://host').pathname;
  const file = contained(path);

  if (file === null) {
    response.writeHead(400).end();
    return;
  }

  // A route without an extension is a client-side route: serve the document, with a fresh nonce.
  if (path === '/' || extname(file) === '') {
    await document(response);
    return;
  }

  try {
    const body = await readFile(file);
    response.writeHead(200, {
      'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream',
      'X-Content-Type-Options': 'nosniff',
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});

server.listen(Number(portArgument), '127.0.0.1', () => {
  console.log(`${app} served with the CSP baseline on http://127.0.0.1:${portArgument}`);
});
