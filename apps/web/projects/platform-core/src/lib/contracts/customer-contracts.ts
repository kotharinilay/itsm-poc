import type { CursorPage, CursorPageQuery } from './paging';
import type { IsoInstant, MessageId, SessionId, WorkItemId } from './primitives';

/**
 * Customer audience (contracts/customer-api.md).
 *
 * Every caller on this audience is an `end_user`, **including a Synoptek staff member** — staff
 * roles are not consulted here and confer nothing (spec FR-SURF-008). Nothing in these types
 * carries a role, and that is deliberate.
 *
 * Note what is absent from every request type: no tenant and no role. Both are derived at the
 * gateway; a client that could supply them could try to widen its own reach.
 */

export type SessionState = 'active' | 'suspended' | 'completed' | 'cancelled' | 'failed';
export type SenderKind = 'end_user' | 'agent' | 'staff';
export type InterruptKind = 'clarification' | 'consent' | 'staff_approval' | 'end_user_approval';

export interface SessionSummary {
  readonly sessionId: SessionId;
  readonly state: SessionState;
  readonly title: string;
  readonly createdAt: IsoInstant;
  readonly updatedAt: IsoInstant;
  /** Present when the session is suspended awaiting this person (spec FR-SESS-018). */
  readonly pendingInterrupt: InterruptKind | null;
}

export interface SessionDetail extends SessionSummary {
  readonly closedAt: IsoInstant | null;
}

export interface ConversationMessage {
  readonly messageId: MessageId;
  readonly senderKind: SenderKind;
  readonly body: string;
  readonly createdAt: IsoInstant;
}

export interface StepTrailEntry {
  readonly stepId: string;
  readonly label: string;
  readonly state: 'pending' | 'running' | 'complete' | 'failed';
  readonly occurredAt: IsoInstant;
}

/** Allow-listed sort fields (contracts/README.md §Sortable and filterable fields). */
export type SessionSortField = 'createdAt' | 'updatedAt' | 'state';
export type MessageSortField = 'createdAt';

export interface SessionListQuery extends CursorPageQuery {
  readonly state?: SessionState;
}

export interface MessageListQuery extends CursorPageQuery {
  readonly senderKind?: SenderKind;
}

export type SessionPage = CursorPage<SessionSummary>;
export type MessagePage = CursorPage<ConversationMessage>;

/** Stream event kinds for the message endpoint, delivered as `text/event-stream`. */
export type StreamEvent =
  | { readonly kind: 'token'; readonly text: string }
  | { readonly kind: 'step'; readonly step: StepTrailEntry }
  // Carries kind and identifiers only. It tells the client a decision is needed; it is not the
  // decision, and the stream ending is not a decision either (contracts/customer-api.md).
  | {
      readonly kind: 'interrupt';
      readonly interrupt: InterruptKind;
      readonly workItemId: WorkItemId;
    }
  | { readonly kind: 'done' }
  | { readonly kind: 'error'; readonly title: string };

export interface StartSessionResponse {
  readonly sessionId: SessionId;
}

/**
 * One turn of conversation.
 *
 * The field is `content`, matching the emitted contract. It was `body` here until Stage 12, which
 * no client could have discovered without sending a turn and getting a 422 — the emitted OpenAPI
 * is the authority, and this file is what it is compared against.
 *
 * **Chat text cannot grant authority** (spec FR-IDENT-004). An affirmative message is never
 * consent — only `POST /work/{id}/consent` records that — so there is no `confirm` field here for
 * a client to set.
 */
export interface SendMessageRequest {
  readonly content: string;
}

/**
 * An answer to a pending clarifying question.
 *
 * Answerable only by the end user of the session (spec FR-INTR-004). Who that is comes from trusted
 * identity, so it is not a field here — and an affirmative answer is not consent.
 */
export interface AnswerRequest {
  readonly content: string;
}

/** Only the work item's requester may consent. An affirmative chat message is never consent. */
export interface ConsentRequest {
  readonly verdict: 'granted' | 'refused';
}

export type FeedbackSignal = 'positive' | 'negative';

export interface FeedbackRequest {
  readonly signal: FeedbackSignal;
}

/**
 * The authorized execution instruction (desktop only). The client verifies catalogue id, catalogue
 * version, content hash and parameters before executing and aborts on any mismatch (ADR-0004).
 * Never delivered over the realtime channel.
 */
export interface ExecutionInstruction {
  readonly workItemId: WorkItemId;
  readonly catalogueId: string;
  readonly catalogueVersion: string;
  readonly contentHash: string;
  readonly parameters: Readonly<Record<string, string>>;
  readonly validUntil: IsoInstant;
}

export interface ExecutionResultRequest {
  readonly workItemId: WorkItemId;
  readonly exitStatus: 'succeeded' | 'failed' | 'aborted';
  readonly summary: string;
}

/** Realtime negotiate. Group membership is derived from identity; a client never names a group. */
export interface RealtimeNegotiateResponse {
  readonly url: string;
  readonly accessToken: string;
  readonly expiresAt: IsoInstant;
}
