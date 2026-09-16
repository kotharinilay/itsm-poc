// @ts-check
import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

/**
 * Lint rules for the Electron desktop host.
 *
 * Most of what matters here is asserted by `tests/` and by
 * `build/scripts/verify-desktop-security-guard.sh`, which are stronger than lint because they fail
 * on behaviour rather than on shape. What lint adds is the class of mistake a test cannot see
 * coming — an API that should never appear anywhere in this package, on any code path, including
 * one nobody has written yet.
 *
 * So the restricted lists below are deliberately absolute. There is no "unless justified" tier:
 * a genuine need for any of them is an architecture change and belongs in an ADR, not in an
 * eslint-disable comment.
 */

/** Node APIs that turn the host into an execution surface. */
const EXECUTION_MODULES = [
  {
    name: 'child_process',
    message:
      'The desktop host executes nothing. Script execution is deferred behind ADR-0004 and lives ' +
      'only as a refusing placeholder in src/main/endpoint-execution-boundary.ts.',
  },
  {
    name: 'node:child_process',
    message:
      'The desktop host executes nothing. Script execution is deferred behind ADR-0004 and lives ' +
      'only as a refusing placeholder in src/main/endpoint-execution-boundary.ts.',
  },
  {
    name: 'vm',
    message: 'No remote or dynamic code execution in the host (constitution Principle VII).',
  },
  {
    name: 'node:vm',
    message: 'No remote or dynamic code execution in the host (constitution Principle VII).',
  },
];

export default tseslint.config(
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**'],
  },

  {
    files: ['**/*.ts'],
    // Deliberately NOT type-aware. The sources here are split across three TypeScript programs —
    // main, preload and tests — and every rule below is syntactic, so a type-aware parser would
    // add a fourth config to keep in sync and buy nothing. Type errors are caught by
    // `npm run typecheck`, which checks both programs properly.
    extends: [eslint.configs.recommended, ...tseslint.configs.recommended],
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      eqeqeq: ['error', 'always'],
      'no-console': ['error', { allow: ['warn', 'error'] }],

      // `eval` and `new Function` are remote code execution with a friendlier name.
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',

      'no-restricted-imports': ['error', { paths: EXECUTION_MODULES }],

      'no-restricted-properties': [
        'error',
        {
          object: 'process',
          property: 'binding',
          message: 'process.binding reaches internals that the sandbox exists to keep away.',
        },
      ],

      // Every one of these disables a control the constitution states unconditionally. A change
      // that needs one is a change that needs an ADR (see docs/adr/README.md).
      'no-restricted-syntax': [
        'error',
        {
          selector: "Property[key.name='webSecurity'][value.value=false]",
          message: 'webSecurity MUST NOT be disabled (constitution Principle VII).',
        },
        {
          selector: "Property[key.name='contextIsolation'][value.value=false]",
          message: 'contextIsolation MUST remain enabled (constitution Principle VII).',
        },
        {
          selector: "Property[key.name='nodeIntegration'][value.value=true]",
          message: 'nodeIntegration MUST remain disabled (constitution Principle VII).',
        },
        {
          selector: "Property[key.name='sandbox'][value.value=false]",
          message: 'Disabling the sandbox requires an ADR (plan Stage 4, docs/adr/README.md).',
        },
        {
          selector: "Property[key.name='allowRunningInsecureContent'][value.value=true]",
          message: 'Insecure content MUST NOT be allowed (constitution Principle VII).',
        },
        {
          selector: "Property[key.name='webviewTag'][value.value=true]",
          message: '<webview> is a second, weaker embedding surface. It stays disabled.',
        },
        {
          selector:
            "CallExpression[callee.object.name='contextBridge'][callee.property.name='exposeInMainWorld'] > Identifier[name='ipcRenderer']",
          message:
            'Raw ipcRenderer MUST NEVER be exposed (constitution Principle VII). Expose a narrow ' +
            'typed function per channel instead.',
        },
      ],
    },
  },

  // The preload is the one file that may import `ipcRenderer` at all — it captures it in a closure
  // so nothing that crosses the bridge can reach it.
  {
    files: ['src/main/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            ...EXECUTION_MODULES,
            {
              name: 'electron',
              importNames: ['ipcRenderer', 'contextBridge'],
              message:
                'ipcRenderer and contextBridge are renderer-side APIs. The main process uses ' +
                'ipcMain, and every handler goes through src/main/ipc-guard.ts.',
            },
          ],
        },
      ],
    },
  },

  // Tests assert on shapes the production rules forbid, and say the forbidden words out loud.
  {
    files: ['tests/**/*.ts'],
    rules: {
      'no-restricted-syntax': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },

  // Build scripts are plain Node ESM, outside the TypeScript program.
  {
    files: ['scripts/**/*.mjs', 'eslint.config.js'],
    extends: [eslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { console: 'readonly', process: 'readonly' },
    },
    rules: {
      // These scripts report what they staged and why they refused; that is their whole output.
      'no-console': 'off',
    },
  },
);
