import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { ApprovalId, SessionId, WorkItemId } from '../contracts/primitives';
import type {
  ApprovalQueuePage,
  ApprovalQueueQuery,
  AuditPage,
  AuditQuery,
  CancelRequest,
  LiveSessionPage,
  LiveSessionQuery,
  PlatformDashboard,
  StaffMessageRequest,
  TakeOverRequest,
  TenantRecord,
  UnexecutedApprovalPage,
  VerdictRequest,
} from '../contracts/staff-contracts';
import { PlatformApiClient, pagingParams } from './platform-api.client';

/**
 * Typed client for the staff audience (contracts/staff-api.md).
 *
 * Structural shells only — paths and types are real, behaviour is not implemented.
 *
 * **There is no method to start a session or raise a request, and there never will be on this
 * audience.** Spec FR-SURF-006: the staff portal exists for staff to work on other people's
 * sessions, not to originate their own. A staff member needing support uses a customer surface,
 * where they are an end user like anyone else. `staff-features.routes.spec.ts` asserts the absence.
 *
 * The target organisation is always derived from the object being operated on, so no method takes
 * a tenant. The `tenantId` on the query types is a narrowing within what the caller can already
 * see — never a widening, and never authority.
 */
@Injectable({ providedIn: 'root' })
export class StaffApiClient {
  private readonly api = inject(PlatformApiClient);

  // ---------------------------------------------------------------- RagCore: commands

  /**
   * Record a verdict. The platform requires a fresh staff token, records the role set held at the
   * time, and returns **before** execution runs — approval is not execution (ADR-0002).
   */
  recordVerdict(approvalId: ApprovalId, request: VerdictRequest): Observable<void> {
    return this.api.post<void, VerdictRequest>(
      `/api/staff/v1/approvals/${approvalId}/verdict`,
      request,
    );
  }

  /**
   * Take over a session: an authenticated state transition, not a socket message. It makes the
   * staff member an additional sender and transfers no requester authority (spec FR-SURF-009).
   */
  takeOverSession(sessionId: SessionId, request: TakeOverRequest): Observable<void> {
    return this.api.post<void, TakeOverRequest>(
      `/api/staff/v1/sessions/${sessionId}/takeover`,
      request,
    );
  }

  sendStaffMessage(sessionId: SessionId, request: StaffMessageRequest): Observable<void> {
    return this.api.post<void, StaffMessageRequest>(
      `/api/staff/v1/sessions/${sessionId}/messages`,
      request,
    );
  }

  /** Permitted before the claim. After it, execution completes and the outcome is recorded. */
  cancelWork(workItemId: WorkItemId, request: CancelRequest): Observable<void> {
    return this.api.post<void, CancelRequest>(`/api/staff/v1/work/${workItemId}/cancel`, request);
  }

  // ---------------------------------------------------------------- .NET: read models

  listLiveSessions(query: LiveSessionQuery = {}): Observable<LiveSessionPage> {
    return this.api.get<LiveSessionPage>('/api/staff/v1/views/sessions/live', {
      ...pagingParams(query),
      state: query.state,
      tenantId: query.tenantId,
    });
  }

  listApprovalQueue(query: ApprovalQueueQuery = {}): Observable<ApprovalQueuePage> {
    return this.api.get<ApprovalQueuePage>('/api/staff/v1/views/approvals/queue', {
      ...pagingParams(query),
      tenantId: query.tenantId,
    });
  }

  /** Approved but never executed — the dead-letter surface (ADR-0002). */
  listUnexecutedApprovals(query: ApprovalQueueQuery = {}): Observable<UnexecutedApprovalPage> {
    return this.api.get<UnexecutedApprovalPage>('/api/staff/v1/views/approvals/unexecuted', {
      ...pagingParams(query),
      tenantId: query.tenantId,
    });
  }

  listAudit(query: AuditQuery = {}): Observable<AuditPage> {
    return this.api.get<AuditPage>('/api/staff/v1/views/audit', {
      ...pagingParams(query),
      tenantId: query.tenantId,
      workItemId: query.workItemId,
      eventKind: query.eventKind,
      occurredFrom: query.occurredFrom,
      occurredTo: query.occurredTo,
    });
  }

  getPlatformDashboard(): Observable<PlatformDashboard> {
    return this.api.get<PlatformDashboard>('/api/staff/v1/views/dashboard/platform');
  }

  listTenants(): Observable<readonly TenantRecord[]> {
    return this.api.get<readonly TenantRecord[]>('/api/staff/v1/views/tenants');
  }
}
