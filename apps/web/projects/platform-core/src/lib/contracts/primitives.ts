/**
 * Shared primitives from the generated API contracts under `build/contracts/`.
 *
 * These are branded rather than bare `string` so an identifier of one kind cannot be passed where
 * another is expected. The platform never trusts a client-supplied identifier regardless; this is
 * to stop the client confusing itself.
 */
declare const brand: unique symbol;
type Branded<T, B extends string> = T & { readonly [brand]: B };

export type TenantId = Branded<string, 'TenantId'>;
export type CorrelationId = Branded<string, 'CorrelationId'>;
export type SessionId = Branded<string, 'SessionId'>;
export type MessageId = Branded<string, 'MessageId'>;
export type WorkItemId = Branded<string, 'WorkItemId'>;
export type ApprovalId = Branded<string, 'ApprovalId'>;
export type ObjectId = Branded<string, 'ObjectId'>;

export const sessionId = (value: string): SessionId => value as SessionId;
export const messageId = (value: string): MessageId => value as MessageId;
export const workItemId = (value: string): WorkItemId => value as WorkItemId;
export const approvalId = (value: string): ApprovalId => value as ApprovalId;
export const correlationId = (value: string): CorrelationId => value as CorrelationId;
export const objectId = (value: string): ObjectId => value as ObjectId;
export const tenantId = (value: string): TenantId => value as TenantId;

/** ISO-8601 instant, always UTC. */
export type IsoInstant = string;

/**
 * Staff roles. Independent capabilities with **no hierarchy** — `administrator` does not imply
 * `technician` (contracts/staff-api.md §Role model).
 *
 * Deliberately a union of string literals and not an enum: an enum invites numeric comparison, and
 * any implementation that sorts, ranks or compares roles is a defect.
 */
export type StaffRole = 'technician' | 'senior_technician' | 'administrator';

export const STAFF_ROLES: readonly StaffRole[] = [
  'technician',
  'senior_technician',
  'administrator',
];

export function isStaffRole(value: string): value is StaffRole {
  return (STAFF_ROLES as readonly string[]).includes(value);
}
