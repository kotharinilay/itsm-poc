import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import type {
  SendMessageRequest,
  StepTrailEntry,
  StreamEvent,
} from '../contracts/customer-contracts';
import { type SessionId, workItemId } from '../contracts/primitives';
import { AuthService } from '../auth/auth.service';
import { CORRELATION_HEADER, CorrelationService } from './correlation';
import { PlatformApiClient } from './platform-api.client';

/**
 * The streaming half of the customer conversation API.
 *
 * `POST /api/customer/v1/sessions/{id}/messages` responds `text/event-stream`, which `HttpClient`
 * cannot consume incrementally — hence `fetch` here and `HttpClient` everywhere else. Because it
 * bypasses the interceptor chain, this class re-applies the two things the chain would have done:
 * the bearer token and `X-Correlation-Id`.
 *
 * ## The stream carries no authority
 *
 * An `interrupt` event tells the client that a decision is needed. It is not the decision. The
 * decision is made by calling the consent or answer endpoint, which authorizes it from scratch. The
 * stream ending is not a decision either (contracts/customer-api.md).
 *
 * Structural shell: the parsing is real so the contract is exercised, and no conversation behaviour
 * is built on it in Stage 3.
 */
@Injectable({ providedIn: 'root' })
export class MessageStreamClient {
  private readonly api = inject(PlatformApiClient);
  private readonly auth = inject(AuthService);
  private readonly correlation = inject(CorrelationService);

  /**
   * Send a message and observe the response as it arrives.
   *
   * Unsubscribing aborts the request, so a surface that navigates away stops the stream rather than
   * leaving it running. Aborting is not a cancellation of the work — disconnection never cancels
   * work or changes any state (spec FR-SESS-017).
   */
  send(sessionId: SessionId, request: SendMessageRequest): Observable<StreamEvent> {
    return new Observable<StreamEvent>((subscriber) => {
      const controller = new AbortController();

      void this.auth
        .accessToken()
        .forEach((token) => this.pump(sessionId, request, token, controller, subscriber))
        .catch((error: unknown) => subscriber.error(error));

      return () => controller.abort();
    });
  }

  private async pump(
    sessionId: SessionId,
    request: SendMessageRequest,
    token: string | null,
    controller: AbortController,
    subscriber: { next(event: StreamEvent): void; error(e: unknown): void; complete(): void },
  ): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      [CORRELATION_HEADER]: this.correlation.next(),
    };
    if (token !== null) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(
        this.api.url(`/api/customer/v1/sessions/${sessionId}/messages`),
        {
          method: 'POST',
          headers,
          body: JSON.stringify(request),
          signal: controller.signal,
        },
      );

      if (!response.ok || response.body === null) {
        subscriber.next({ kind: 'error', title: `The platform returned ${response.status}` });
        subscriber.complete();
        return;
      }

      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += value;

        // SSE frames are separated by a blank line.
        let separator = buffer.indexOf('\n\n');
        while (separator !== -1) {
          const frame = buffer.slice(0, separator);
          buffer = buffer.slice(separator + 2);
          const event = parseFrame(frame);
          if (event !== null) {
            subscriber.next(event);
          }
          separator = buffer.indexOf('\n\n');
        }
      }
      subscriber.complete();
    } catch (error: unknown) {
      if (controller.signal.aborted) {
        subscriber.complete();
        return;
      }
      subscriber.error(error);
    }
  }
}

/** Parse one SSE frame into a typed event. An unrecognised frame is dropped, never guessed at. */
export function parseFrame(frame: string): StreamEvent | null {
  const dataLines = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim());

  if (dataLines.length === 0) {
    return null;
  }

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join('\n'));
  } catch {
    return null;
  }

  return toStreamEvent(payload);
}

function toStreamEvent(payload: unknown): StreamEvent | null {
  if (typeof payload !== 'object' || payload === null) {
    return null;
  }
  const candidate = payload as Record<string, unknown>;

  switch (candidate['kind']) {
    case 'token':
      return typeof candidate['text'] === 'string'
        ? { kind: 'token', text: candidate['text'] }
        : null;
    case 'step':
      return isStep(candidate['step']) ? { kind: 'step', step: candidate['step'] } : null;
    case 'interrupt':
      return typeof candidate['interrupt'] === 'string' &&
        typeof candidate['workItemId'] === 'string'
        ? {
            kind: 'interrupt',
            interrupt: candidate['interrupt'] as StreamEvent extends { interrupt: infer K }
              ? K
              : never,
            workItemId: workItemId(candidate['workItemId']),
          }
        : null;
    case 'done':
      return { kind: 'done' };
    case 'error':
      return {
        kind: 'error',
        title: typeof candidate['title'] === 'string' ? candidate['title'] : 'Stream failed',
      };
    default:
      return null;
  }
}

function isStep(value: unknown): value is StepTrailEntry {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return typeof candidate['stepId'] === 'string' && typeof candidate['label'] === 'string';
}
