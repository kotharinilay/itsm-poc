import { Injectable, computed, inject, signal } from '@angular/core';
import { EMPTY, Observable, filter } from 'rxjs';
import { type NotificationEnvelope, isNotificationEnvelope } from './notification-envelope';
import {
  REALTIME_CONNECTION,
  type RealtimeConnection,
  type RealtimeStatus,
} from './realtime-connection';

/**
 * The one realtime integration point for all three surfaces.
 *
 * Centralised per FE-NG-4 (.claude/rules/23-angular.md): realtime/SignalR infrastructure is
 * centralized rather
 * than repeated.
 *
 * ## Reconnect rebuilds from the platform, not from missed notifications
 *
 * Spec FR-SESS-019 is the requirement this class is shaped around. A client that reconnects and
 * replays a backlog is trusting the channel to be complete, and the channel is explicitly allowed
 * to drop messages — the platform continues without it. So there is **no buffer and no replay
 * here**. On every reconnect this service raises `resyncRequired`, and the surface responds by
 * re-reading the API. A missed notification then delays awareness and nothing more.
 *
 * ## The channel carries no authority
 *
 * A notification says something changed. Any consequential action taken in response is an
 * authenticated API request, authorized from scratch as if no notification had been sent (spec
 * FR-SURF-018). Nothing on this service returns a decision, and nothing here grants anything.
 */
@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private readonly connection = inject<RealtimeConnection | null>(REALTIME_CONNECTION, {
    optional: true,
  });

  private readonly statusSignal = signal<RealtimeStatus>('disconnected');
  /** Increments on every reconnect. A surface watches it and re-reads from the API. */
  private readonly resyncSignal = signal(0);

  readonly status = this.statusSignal.asReadonly();
  readonly resyncRequired = this.resyncSignal.asReadonly();
  readonly isConnected = computed(() => this.statusSignal() === 'connected');

  /** Validated envelopes. Anything that does not match the contract is dropped, never coerced. */
  readonly notifications$: Observable<NotificationEnvelope> =
    this.connection === null
      ? EMPTY
      : this.connection.messages$.pipe(filter(isNotificationEnvelope));

  constructor() {
    this.connection?.status$.subscribe((status) => this.onStatus(status));
  }

  async connect(): Promise<void> {
    await this.connection?.start();
  }

  async disconnect(): Promise<void> {
    await this.connection?.stop();
  }

  /**
   * Notifications of a particular kind. A convenience filter — subscribing to one still tells the
   * subscriber only that something changed.
   */
  ofKind(kind: NotificationEnvelope['kind']): Observable<NotificationEnvelope> {
    return this.notifications$.pipe(filter((envelope) => envelope.kind === kind));
  }

  private onStatus(status: RealtimeStatus): void {
    const previous = this.statusSignal();
    this.statusSignal.set(status);

    // Re-establishing the connection means the client may have missed messages while it was away.
    // It does not try to find out which ones: it asks the platform for the current truth instead.
    if (status === 'connected' && previous === 'reconnecting') {
      this.resyncSignal.update((count) => count + 1);
    }
  }
}
