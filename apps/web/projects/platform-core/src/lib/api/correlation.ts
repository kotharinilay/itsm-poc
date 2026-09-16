import { Injectable, signal } from '@angular/core';
import { type CorrelationId, correlationId } from '../contracts/primitives';

/** The header the edge accepts and echoes (contracts/README.md §Conventions). */
export const CORRELATION_HEADER = 'X-Correlation-Id';

/**
 * Issues and remembers correlation identifiers.
 *
 * One identifier ties a request to every trigger, notification, log, span and audit record it
 * causes. Centralised here so no caller has to remember to generate one — a request without a
 * correlation id is one nobody can trace afterwards.
 */
@Injectable({ providedIn: 'root' })
export class CorrelationService {
  private readonly last = signal<CorrelationId | null>(null);

  /** The most recently issued identifier, for surfacing on an error screen. */
  readonly lastIssued = this.last.asReadonly();

  next(): CorrelationId {
    const value = correlationId(this.newId());
    this.last.set(value);
    return value;
  }

  private newId(): string {
    const cryptoApi = globalThis.crypto as Crypto | undefined;
    if (cryptoApi !== undefined && typeof cryptoApi.randomUUID === 'function') {
      return cryptoApi.randomUUID();
    }
    // Fallback for a context without `crypto.randomUUID`. A correlation id is a tracing handle, not
    // a secret and not authority-bearing, so unpredictability is not a requirement here.
    return `cid-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }
}
