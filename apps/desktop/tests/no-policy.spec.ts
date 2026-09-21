/**
 * T056 — no business authorization decision exists in the renderer **or** the main process.
 *
 * FE-EL-1 (.claude/rules/24-electron.md) states this unconditionally, and FE-EL-11 sharpens it
 * for the endpoint: the endpoint executes; it MUST NEVER decide. This suite is the thing that fails when
 * that stops being true.
 *
 * Two kinds of assertion here, and they catch different things:
 *
 *  1. **Structural** — over the exported contract and boundary descriptors. Precise, and the first
 *     to break when a channel or a descriptor field is added.
 *  2. **Source-level** — a scan of the main and preload sources for the vocabulary of authorization
 *     appearing in *code* rather than in prose. Blunter, but it catches a decision smuggled into a
 *     module that exports nothing new. Comments and string literals are stripped first, because
 *     this file and its siblings discuss authorization constantly and a guard that flags its own
 *     documentation is a guard somebody disables.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { BRIDGE_SURFACE, IPC_CHANNELS } from '../src/ipc-contracts/index.js';
import {
  HOST_SESSION_PROHIBITIONS,
  SESSION_BOUNDARY,
  describeSessionBoundary,
} from '../src/main/session-boundary.js';
import {
  EndpointExecutionNotImplementedError,
  EXECUTION_PRECONDITIONS,
  IS_IMPLEMENTED,
  executeApprovedScript,
  verifyScriptBindings,
} from '../src/main/endpoint-execution-boundary.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(here, '..', 'src');

/** Read every TypeScript source under `src/`, with comments and string literals removed. */
function executableSources(): ReadonlyArray<{ file: string; code: string }> {
  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith('.ts')) {
        files.push(full);
      }
    }
  };
  walk(SRC);

  return files.map((file) => ({
    file: path.relative(SRC, file).replace(/\\/g, '/'),
    code: fs
      .readFileSync(file, 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/\/\/.*$/gm, ' ')
      .replace(/'(?:[^'\\]|\\.)*'/g, "''")
      .replace(/"(?:[^"\\]|\\.)*"/g, '""')
      .replace(/`(?:[^`\\]|\\.)*`/g, '``'),
  }));
}

describe('the IPC contract exposes no authority', () => {
  const authorityWords = [
    'role',
    'permission',
    'approve',
    'approval',
    'tenant',
    'authoriz',
    'consent',
    'entitle',
    'grant',
    'token',
  ];

  it.each(authorityWords)('names no channel containing %s', (word) => {
    for (const channel of IPC_CHANNELS) {
      expect(channel.toLowerCase()).not.toContain(word);
    }
  });

  it.each(authorityWords)('names no bridge member containing %s', (word) => {
    for (const member of Object.keys(BRIDGE_SURFACE)) {
      expect(member.toLowerCase()).not.toContain(word);
    }
  });

  it('exposes no script-execution channel — the endpoint path is deferred (ADR-0004)', () => {
    for (const channel of IPC_CHANNELS) {
      expect(channel.toLowerCase()).not.toContain('script');
      expect(channel.toLowerCase()).not.toContain('exec');
      expect(channel.toLowerCase()).not.toContain('run');
      expect(channel.toLowerCase()).not.toContain('spawn');
    }
  });
});

describe('no decision vocabulary appears in main or preload code', () => {
  /**
   * Identifiers that would indicate a decision being *made* rather than a subject being named.
   * Matched against code with comments and strings stripped, so prose about the rule is exempt.
   */
  const decisionIdentifiers = [
    /\bis(?:User)?Authoriz(?:ed|e)\b/i,
    /\bcanApprove\b/i,
    /\bhasRole\b/i,
    /\bhasPermission\b/i,
    /\bcheckPermission\b/i,
    /\bisPermitted\b/i,
    /\bassertRole\b/i,
    /\brequireRole\b/i,
    /\bcurrentTenant\b/i,
    /\bresolveTenant\b/i,
    /\baccessToken\b/i,
    /\bbearerToken\b/i,
  ];

  it.each(decisionIdentifiers.map((r) => [r.source, r] as const))(
    'no source matches %s',
    (_label, pattern) => {
      for (const { file, code } of executableSources()) {
        expect(`${file}: ${pattern.test(code) ? 'MATCH' : 'clean'}`).toBe(`${file}: clean`);
      }
    },
  );

  it('calls no child-process, shell-execution or dynamic-evaluation API', () => {
    const forbidden = [
      /\bchild_process\b/,
      /\bexecSync?\b/,
      /\bexecFile\b/,
      /\bspawnSync?\b/,
      /\bnew Function\b/,
      /\beval\s*\(/,
      /\bvm\.runIn/,
    ];
    for (const { file, code } of executableSources()) {
      for (const pattern of forbidden) {
        expect(`${file}: ${pattern.test(code) ? `MATCH ${pattern.source}` : 'clean'}`).toBe(
          `${file}: clean`,
        );
      }
    }
  });

  it('never disables a security switch anywhere in the tree', () => {
    const forbidden = [
      /webSecurity\s*:\s*false/,
      /contextIsolation\s*:\s*false/,
      /nodeIntegration\s*:\s*true/,
      /sandbox\s*:\s*false/,
      /allowRunningInsecureContent\s*:\s*true/,
      /webviewTag\s*:\s*true/,
    ];
    for (const { file, code } of executableSources()) {
      for (const pattern of forbidden) {
        expect(`${file}: ${pattern.test(code) ? `MATCH ${pattern.source}` : 'clean'}`).toBe(
          `${file}: clean`,
        );
      }
    }
  });
});

describe('the desktop session integration boundary decides nothing', () => {
  it('places token custody in the renderer and authority with the platform', () => {
    expect(SESSION_BOUNDARY.tokenCustody).toBe('renderer');
    expect(SESSION_BOUNDARY.authorityHolder).toBe('platform');
  });

  it('persists no session state in the main process', () => {
    expect(SESSION_BOUNDARY.mainProcessPersistsSession).toBe(false);
  });

  it('returns a constant — the descriptor is a shape, never a session', () => {
    expect(describeSessionBoundary()).toBe(SESSION_BOUNDARY);
    expect(Object.isFrozen(SESSION_BOUNDARY)).toBe(true);
  });

  it('records what the host must never do, so the list survives a refactor', () => {
    expect(HOST_SESSION_PROHIBITIONS.length).toBeGreaterThan(0);
    expect(HOST_SESSION_PROHIBITIONS.join(' ')).toContain('permitted');
  });

  it('exposes no field carrying identity, tenancy or a verdict', () => {
    const forbidden = ['userId', 'tenantId', 'roles', 'token', 'isSignedIn', 'permitted'];
    for (const key of Object.keys(SESSION_BOUNDARY)) {
      expect(forbidden).not.toContain(key);
    }
  });
});

describe('the endpoint execution boundary is a placeholder and refuses', () => {
  const instruction = {
    workItemId: 'wi-1',
    catalogueEntryId: 'cat-1',
    version: '1.0.0',
    contentHash: 'sha256-deadbeef',
  };

  it('reports itself as unimplemented', () => {
    expect(IS_IMPLEMENTED).toBe(false);
  });

  it('throws on execution, with a well-formed instruction', () => {
    expect(() => executeApprovedScript(instruction)).toThrow(EndpointExecutionNotImplementedError);
  });

  it('throws on binding verification too — the two stay separate functions', () => {
    expect(() => verifyScriptBindings(instruction, 'sha256-deadbeef')).toThrow(
      EndpointExecutionNotImplementedError,
    );
  });

  it('records the four bindings a real instruction must carry', () => {
    expect(Object.keys(instruction).sort()).toEqual([
      'catalogueEntryId',
      'contentHash',
      'version',
      'workItemId',
    ]);
  });

  it('names server-side authority as a precondition, not something it evaluates', () => {
    expect(EXECUTION_PRECONDITIONS.join(' ')).toContain('Server-side authority exists');
    expect(EXECUTION_PRECONDITIONS.join(' ')).toContain('ADR-0004');
  });

  it('is reachable from no IPC channel', () => {
    const sourceOfMain = executableSources().filter(({ file }) => file.startsWith('main/'));
    const shell = sourceOfMain.find(({ file }) => file === 'main/app-shell.ts');
    expect(shell?.code).not.toContain('endpoint-execution-boundary');
    const preload = executableSources().filter(({ file }) => file.startsWith('preload/'));
    for (const { code } of preload) {
      expect(code).not.toContain('endpoint-execution-boundary');
    }
  });
});
