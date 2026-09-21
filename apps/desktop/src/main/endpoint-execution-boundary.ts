/**
 * The endpoint execution boundary — **a placeholder. Nothing here executes anything.**
 *
 * Plan Stage 4's non-goals are explicit: no script execution, the catalogue is empty. ADR-0004's
 * open items — script signing and the destructive-operation taxonomy — are unresolved, and no use
 * case may touch the desktop path before they are. This file is the seam where that path will one
 * day attach, written now so the *shape* of the obligation is recorded while the implementation is
 * still refused.
 *
 * ## What FE-EL-11 (.claude/rules/24-electron.md) requires of this path, when it is eventually built
 *
 *  - Scripts are **predefined, versioned and platform-owned**. The platform must not generate them
 *    at runtime, and the endpoint must not compose them.
 *  - Scripts are **fetched per execution** and must not be cached locally.
 *  - The instruction **binds four things**: work item, catalogue entry, version and content hash.
 *    A mismatch on **any** of the four aborts before execution.
 *  - Script handling stays in the **main process** and never reaches the renderer.
 *  - Scripts run **as the signed-in user** and never elevated.
 *  - The endpoint executes only after **server-side authority already exists**. It never decides
 *    whether an operation is permitted. *(Principle VII; Principle III: "The endpoint executes; it
 *    MUST NEVER decide.")*
 *
 * ## What this file does
 *
 * It declares the instruction type and refuses. `executeApprovedScript` throws unconditionally —
 * there is no configuration, environment variable or argument that makes it do otherwise, and
 * `tests/endpoint-boundary.spec.ts` asserts exactly that. No IPC channel reaches it, so the
 * renderer cannot call it even indirectly.
 *
 * A placeholder that silently did nothing would be worse than this one: it would let a caller be
 * written against a function that appears to succeed. This one fails loudly at the call site.
 */

/**
 * The four bindings a real instruction must carry.
 *
 * Declared now so the type exists for contract work upstream, and so the four-field requirement is
 * visible in the codebase rather than only in the rule. Every field is required: there is
 * no partial instruction.
 */
export interface ApprovedScriptInstruction {
  /** The work item this execution belongs to. */
  readonly workItemId: string;
  /** The catalogue entry naming the predefined, platform-owned script. */
  readonly catalogueEntryId: string;
  /** The exact version of that entry. A range is not a version. */
  readonly version: string;
  /** The hash of the script content, verified against the fetched body before execution. */
  readonly contentHash: string;
}

/** Thrown by every entry point in this module. */
export class EndpointExecutionNotImplementedError extends Error {
  public override readonly name = 'EndpointExecutionNotImplementedError';
  public constructor() {
    super(
      'Endpoint script execution is not implemented. It is blocked on ADR-0004 (script signing ' +
        'and the destructive-operation taxonomy) and on both golden paths validating. See ' +
        'ADR-0004 and ADR-0006.',
    );
  }
}

/**
 * The preconditions that must hold before a single line of execution code is written.
 *
 * Data, not prose, so the test suite can assert the list is non-empty and that the boundary still
 * refuses while any of it stands.
 */
export const EXECUTION_PRECONDITIONS: readonly string[] = Object.freeze([
  'ADR-0004 open item: script signing is resolved',
  'ADR-0004 open item: the destructive-operation taxonomy is resolved',
  'Server-side authority exists for the specific work item, operation, target and version',
  'The approval is inside its fifteen-minute execution validity window',
  'The catalogue entry is predefined, versioned and platform-owned',
  'The fetched script body matches the instruction content hash',
  'Both architectural golden paths validate (plan Stages 12 and 13)',
]);

/** Whether this boundary is implemented. Constant `false`, and asserted to be. */
export const IS_IMPLEMENTED = false;

/**
 * Execute an approved script. **Always throws.**
 *
 * The parameter is accepted and typed so callers are written against the real shape, and then
 * ignored — because accepting it and acting on it are different things, and only the first is
 * permitted here. There is no branch in this function.
 */
export function executeApprovedScript(_instruction: ApprovedScriptInstruction): never {
  throw new EndpointExecutionNotImplementedError();
}

/**
 * Verify the four bindings.
 *
 * Also unimplemented, and separate from execution on purpose: when this path is built, verification
 * and execution must remain two functions, so that "a mismatch on any of the four aborts before
 * execution" is a property of the code's structure rather than of a reviewer's attention.
 */
export function verifyScriptBindings(
  _instruction: ApprovedScriptInstruction,
  _fetchedContentHash: string,
): never {
  throw new EndpointExecutionNotImplementedError();
}
