import type { CorrelationId, IsoInstant, SessionId, WorkItemId } from '../contracts/primitives';

/**
 * The SignalR envelope (contracts/notifications.md).
 *
 * **SignalR is a leaf on every consequential path, never a link.** An envelope may say that
 * something exists or has changed. It may never carry, imply or trigger a decision.
 *
 * Look at what this type does not have: no tenant, no role, no approval state, no target, no
 * command content. The envelope carries no authority-bearing value, so a consumer cannot read
 * authority from it even by mistake — there is nothing there to read.
 */
export type NotificationKind =
  | 'interrupt.pending'
  | 'approval.decided'
  | 'work.progressed'
  | 'work.completed'
  | 'work.failed'
  | 'instruction.ready'
  | 'session.taken_over';

export interface NotificationEnvelope {
  readonly kind: NotificationKind;
  readonly occurredAt: IsoInstant;
  /** Always present. Ties the notification to the originating request and to audit. */
  readonly correlationId: CorrelationId;
  /** Opaque. The client fetches detail through an authenticated API call. */
  readonly sessionId?: SessionId;
  readonly workItemId?: WorkItemId;
}

const KINDS: ReadonlySet<string> = new Set<NotificationKind>([
  'interrupt.pending',
  'approval.decided',
  'work.progressed',
  'work.completed',
  'work.failed',
  'instruction.ready',
  'session.taken_over',
]);

/**
 * Validate an inbound envelope.
 *
 * A message that does not match is dropped rather than coerced. The channel is unauthenticated
 * input as far as this client is concerned — and since nothing consequential depends on it,
 * dropping one costs awareness and nothing else.
 */
export function isNotificationEnvelope(value: unknown): value is NotificationEnvelope {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate['kind'] === 'string' &&
    KINDS.has(candidate['kind']) &&
    typeof candidate['occurredAt'] === 'string' &&
    typeof candidate['correlationId'] === 'string'
  );
}
