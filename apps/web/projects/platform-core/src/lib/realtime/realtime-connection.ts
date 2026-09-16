import { InjectionToken } from '@angular/core';
import type { Observable } from 'rxjs';

/** Connection lifecycle, as the client observes it. */
export type RealtimeStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

/**
 * The transport seam.
 *
 * Declared as a port so `@microsoft/signalr` is integrated in exactly one adapter rather than
 * imported across features. The scaffold registers no implementation: Stage 8 brings the hub, and
 * pretending otherwise would be a dishonest scaffold (constitution P-IX).
 */
export interface RealtimeConnection {
  readonly status$: Observable<RealtimeStatus>;
  /** Raw inbound payloads. Validation and typing happen above this seam. */
  readonly messages$: Observable<unknown>;

  start(): Promise<void>;
  stop(): Promise<void>;
}

export const REALTIME_CONNECTION = new InjectionToken<RealtimeConnection>('REALTIME_CONNECTION');
