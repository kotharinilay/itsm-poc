import type { ObjectId, StaffRole } from '../contracts/primitives';

/**
 * What the client knows about the signed-in person.
 *
 * Every field here is **display state**. None of it is authority. The platform derives identity,
 * organisation and roles at the gateway on every request and re-decides authorization from scratch
 * (spec FR-SURF-004, FR-SURF-005). Nothing a client puts in this object can widen what it may do.
 *
 * Note the absence of a tenant. Organisation is never a client concern and never a parameter
 * (contracts/README.md rule 1), so it is not modelled here at all — a field that does not exist
 * cannot be sent.
 */
export interface AuthSession {
  readonly objectId: ObjectId;
  readonly displayName: string;

  /**
   * Roles reported by the identity provider, for menu visibility only.
   *
   * Empty on a customer surface — and deliberately so: every person acting on a customer surface is
   * an end user regardless of any staff role they hold, and holding one confers nothing there
   * (spec FR-SURF-008).
   */
  readonly roles: readonly StaffRole[];
}

export type AuthStatus = 'unknown' | 'signed-out' | 'signed-in';
