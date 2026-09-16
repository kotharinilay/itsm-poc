import type { SessionState } from './customer-contracts';
import type { CursorPage, CursorPageQuery } from './paging';
import type {
  ApprovalId,
  IsoInstant,
  SessionId,
  StaffRole,
  TenantId,
  WorkItemId,
} from './primitives';

/**
 * Staff audience (contracts/staff-api.md). Reachable only from the staff portal.
 *
 * The target organisation is **always** derived from the platform object being operated on, never
 * supplied by the caller — so no request type here carries a tenant.
 *
 * `tenantId` appears on the *query* types below only as a staff-only narrowing within what the
 * caller may already see. It is not a tenant parameter and establishes no authority.
 */

export interface ApprovalQueueEntry {
  readonly approvalId: ApprovalId;
  readonly workItemId: WorkItemId;
  readonly sessionId: SessionId;
  readonly tenantId: TenantId;
  /** The full command as disclosed to the approver. Never abbreviated in the queue. */
  readonly disclosedCommand: string;
  readonly requestedAt: IsoInstant;
  readonly expiresAt: IsoInstant;
}

export interface UnexecutedApproval {
  readonly approvalId: ApprovalId;
  readonly workItemId: WorkItemId;
  readonly tenantId: TenantId;
  readonly decidedAt: IsoInstant;
  readonly expiresAt: IsoInstant;
}

export interface LiveSession {
  readonly sessionId: SessionId;
  readonly tenantId: TenantId;
  readonly state: SessionState;
  readonly createdAt: IsoInstant;
  readonly updatedAt: IsoInstant;
  readonly hasStaffParticipant: boolean;
}

export interface AuditEntry {
  readonly auditId: string;
  readonly tenantId: TenantId;
  readonly workItemId: WorkItemId | null;
  readonly eventKind: string;
  readonly occurredAt: IsoInstant;
  readonly actorObjectId: string | null;
}

export interface TenantRecord {
  readonly tenantId: TenantId;
  readonly displayName: string;
  readonly status: 'active' | 'suspended';
}

export interface PlatformDashboard {
  readonly generatedAt: IsoInstant;
  readonly activeSessions: number;
  readonly pendingApprovals: number;
  readonly unexecutedApprovals: number;
}

export type ApprovalQueueSortField = 'createdAt' | 'expiresAt';
export type UnexecutedSortField = 'decidedAt' | 'expiresAt';
export type LiveSessionSortField = 'createdAt' | 'updatedAt' | 'state';
export type AuditSortField = 'occurredAt';

export interface ApprovalQueueQuery extends CursorPageQuery {
  readonly tenantId?: TenantId;
}

export interface LiveSessionQuery extends CursorPageQuery {
  readonly state?: SessionState;
  readonly tenantId?: TenantId;
}

export interface AuditQuery extends CursorPageQuery {
  readonly tenantId?: TenantId;
  readonly workItemId?: WorkItemId;
  readonly eventKind?: string;
  readonly occurredFrom?: IsoInstant;
  readonly occurredTo?: IsoInstant;
}

export type ApprovalQueuePage = CursorPage<ApprovalQueueEntry>;
export type UnexecutedApprovalPage = CursorPage<UnexecutedApproval>;
export type LiveSessionPage = CursorPage<LiveSession>;
export type AuditPage = CursorPage<AuditEntry>;

/**
 * A verdict requires a fresh staff token and is recorded with the role set held at the time. The
 * request returns before execution runs; approval is not execution.
 */
export interface VerdictRequest {
  readonly verdict: 'approved' | 'rejected';
  readonly note?: string;
}

/**
 * Take-over makes the staff member an additional sender in the end user's session. It does **not**
 * transfer requester authority (spec FR-SURF-009).
 */
export interface TakeOverRequest {
  readonly reason: string;
}

export interface StaffMessageRequest {
  readonly body: string;
}

export interface CancelRequest {
  readonly reason: string;
}

/**
 * The roles each staff operation accepts, mirrored from contracts/staff-api.md for presentation.
 *
 * This is a **convenience mirror, not the decision**. The platform re-decides every one of these
 * server-side by set intersection, and a client that disagrees with this table simply shows the
 * wrong menu — it cannot grant anything (spec FR-SURF-004).
 */
export const STAFF_OPERATION_ROLES = {
  approvalVerdict: ['technician'],
  takeOver: ['technician'],
  staffMessage: ['technician'],
  cancelWork: ['technician'],
  viewLiveSessions: ['technician'],
  viewApprovalQueue: ['technician'],
  viewUnexecutedApprovals: ['technician'],
  viewAudit: ['technician'],
  viewPlatformDashboard: ['administrator'],
  viewTenants: ['administrator'],
} as const satisfies Readonly<Record<string, readonly StaffRole[]>>;

export type StaffOperation = keyof typeof STAFF_OPERATION_ROLES;
