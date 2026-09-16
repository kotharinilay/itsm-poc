import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  AnswerRequest,
  ConsentRequest,
  ExecutionInstruction,
  ExecutionResultRequest,
  FeedbackRequest,
  MessageListQuery,
  MessagePage,
  RealtimeNegotiateResponse,
  SessionDetail,
  SessionListQuery,
  SessionPage,
  StartSessionResponse,
  StepTrailEntry,
} from '../contracts/customer-contracts';
import type { MessageId, SessionId, WorkItemId } from '../contracts/primitives';
import { PlatformApiClient, pagingParams } from './platform-api.client';

/**
 * Typed client for the customer audience (contracts/customer-api.md).
 *
 * Every method here is a **shell**: the path, the request type and the response type are real and
 * match the contract, and there is no business behaviour behind any of them. Stage 3 wires the
 * surface; the backends arrive in Stages 5 and 6.
 *
 * No method takes a tenant or a role. Both are derived at the gateway and are never parameters
 * (contracts/README.md rule 1) — so there is no argument through which a client could try to
 * supply one.
 */
@Injectable({ providedIn: 'root' })
export class CustomerApiClient {
  private readonly api = inject(PlatformApiClient);

  // ---------------------------------------------------------------- RagCore: conversation

  startSession(): Observable<StartSessionResponse> {
    return this.api.post<StartSessionResponse>('/api/customer/v1/sessions');
  }

  /**
   * The streaming message endpoint responds `text/event-stream`, so it is deliberately absent from
   * this class: `HttpClient` is the wrong tool for it. `MessageStreamClient` owns that path and
   * returns typed `StreamEvent`s.
   */
  answerClarification(sessionId: SessionId, request: AnswerRequest): Observable<void> {
    return this.api.post<void, AnswerRequest>(
      `/api/customer/v1/sessions/${sessionId}/answers`,
      request,
    );
  }

  /**
   * Record consent. Only the work item's requester may do this, and the platform enforces that —
   * an affirmative chat message is never consent, and consent never satisfies a `STAFF_APPROVAL`
   * requirement.
   */
  recordConsent(workItemId: WorkItemId, request: ConsentRequest): Observable<void> {
    return this.api.post<void, ConsentRequest>(
      `/api/customer/v1/work/${workItemId}/consent`,
      request,
    );
  }

  /**
   * Fetch the authorized execution instruction. Desktop only, and never delivered over the realtime
   * channel. The caller verifies catalogue id, version, content hash and parameters before
   * executing, and aborts on any mismatch (ADR-0004). Returns 410 once the window has elapsed.
   */
  fetchInstruction(workItemId: WorkItemId): Observable<ExecutionInstruction> {
    return this.api.get<ExecutionInstruction>(`/api/customer/v1/work/${workItemId}/instruction`);
  }

  postExecutionResult(workItemId: WorkItemId, request: ExecutionResultRequest): Observable<void> {
    return this.api.post<void, ExecutionResultRequest>(
      `/api/customer/v1/work/${workItemId}/result`,
      request,
    );
  }

  /** Feedback is revisable, so `PUT` replaces rather than appends. */
  recordFeedback(messageId: MessageId, request: FeedbackRequest): Observable<void> {
    return this.api.put<void, FeedbackRequest>(
      `/api/customer/v1/messages/${messageId}/feedback`,
      request,
    );
  }

  withdrawFeedback(messageId: MessageId): Observable<void> {
    return this.api.delete<void>(`/api/customer/v1/messages/${messageId}/feedback`);
  }

  /** Group membership is derived from identity at negotiation; a client never names a group. */
  negotiateRealtime(): Observable<RealtimeNegotiateResponse> {
    return this.api.post<RealtimeNegotiateResponse>('/api/customer/v1/realtime/negotiate');
  }

  // ---------------------------------------------------------------- .NET: read models

  listSessions(query: SessionListQuery = {}): Observable<SessionPage> {
    return this.api.get<SessionPage>('/api/customer/v1/views/sessions', {
      ...pagingParams(query),
      state: query.state,
    });
  }

  getSession(sessionId: SessionId): Observable<SessionDetail> {
    return this.api.get<SessionDetail>(`/api/customer/v1/views/sessions/${sessionId}`);
  }

  listMessages(sessionId: SessionId, query: MessageListQuery = {}): Observable<MessagePage> {
    return this.api.get<MessagePage>(`/api/customer/v1/views/sessions/${sessionId}/messages`, {
      ...pagingParams(query),
      senderKind: query.senderKind,
    });
  }

  listSteps(sessionId: SessionId): Observable<readonly StepTrailEntry[]> {
    return this.api.get<readonly StepTrailEntry[]>(
      `/api/customer/v1/views/sessions/${sessionId}/steps`,
    );
  }
}
