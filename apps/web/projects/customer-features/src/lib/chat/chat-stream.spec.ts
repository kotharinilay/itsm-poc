import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LiveAnnouncer } from 'design-system';
import {
  MessageStreamClient,
  PLATFORM_API_CONFIG,
  sessionId,
  workItemId,
  type StreamEvent,
} from 'platform-core';
import { Subject } from 'rxjs';
import { ChatShell } from './chat-shell';

/**
 * The chat surface's consumption of the SSE stream.
 *
 * Two families of assertion, and the second is the one that matters:
 *
 * * **Accessibility** (`FR-SURF-011`): progressive content is announced as it arrives, announcing
 *   only what is new. The failure this guards against is the naive one — writing the accumulated
 *   response into a live region on every token, so a screen reader reads the answer back from the
 *   beginning each time.
 * * **The stream carries no authority**: an `interrupt` frame is recorded and announced and
 *   **enables nothing**, and `done` is not a statement that anything was authorized or resolved.
 */
const SESSION = sessionId('22222222-2222-2222-2222-222222222222');

class StubStream {
  readonly events = new Subject<StreamEvent>();
  readonly sent: string[] = [];

  send(_session: unknown, request: { content: string }): Subject<StreamEvent> {
    this.sent.push(request.content);
    return this.events;
  }
}

describe('ChatShell streaming', () => {
  let fixture: ComponentFixture<ChatShell>;
  let shell: ChatShell & Record<string, never>;
  let stream: StubStream;
  let announced: string[];

  beforeEach(async () => {
    stream = new StubStream();

    await TestBed.configureTestingModule({
      imports: [ChatShell],
      providers: [
        provideHttpClient(),
        { provide: MessageStreamClient, useValue: stream },
        {
          provide: PLATFORM_API_CONFIG,
          useValue: {
            gatewayOrigin: 'https://api.test.example',
            authAuthority: 'https://login.microsoftonline.com',
            authClientId: 'client-id',
            authScopes: [],
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatShell);
    shell = fixture.componentInstance as ChatShell & Record<string, never>;

    announced = [];
    const announcer = TestBed.inject(LiveAnnouncer);
    spyOn(announcer, 'announce').and.callFake((message: string) => {
      announced.push(message);
    });
    spyOn(announcer, 'announceDelta').and.callFake((_key: string, full: string) => {
      const previous = announced.filter((entry) => full.startsWith(entry)).pop() ?? '';
      const delta = full.slice(previous.length);
      announced.push(full);
      return delta;
    });

    fixture.detectChanges();
  });

  const send = (): void => {
    (shell as unknown as { send(id: unknown, text: string): void }).send(
      SESSION,
      'my vpn will not connect',
    );
  };

  const state = <T>(name: string): T =>
    (shell as unknown as Record<string, () => T>)[name]!.call(shell);

  it('sends the turn as `content`, matching the emitted contract', () => {
    send();
    expect(stream.sent).toEqual(['my vpn will not connect']);
  });

  it('accumulates token text for display', () => {
    send();
    stream.events.next({ kind: 'token', text: 'Reapply ' });
    stream.events.next({ kind: 'token', text: 'the profile.' });
    fixture.detectChanges();

    expect(state<string>('streamed')).toBe('Reapply the profile.');
  });

  it('announces only what is new, never the whole message again', () => {
    send();
    stream.events.next({ kind: 'token', text: 'Reapply ' });
    stream.events.next({ kind: 'token', text: 'the profile.' });

    // The announcer is handed the ACCUMULATION and computes the delta, so a server that one day
    // sent the whole message would still not make a screen reader re-read it.
    expect(announced).toEqual(['Reapply ', 'Reapply the profile.']);
  });

  it('records an interrupt without enabling anything', () => {
    send();
    stream.events.next({
      kind: 'interrupt',
      interrupt: 'staff_approval',
      workItemId: workItemId('33333333-3333-3333-3333-333333333333'),
    });
    fixture.detectChanges();

    expect(state<string | null>('pendingInterrupt')).toBe('staff_approval');
    // Announced as a sentence, not as its identifier.
    expect(announced.some((entry) => entry.includes('support team'))).toBe(true);
    // The rendered notice carries the machine-readable kind, so state is conveyed by more than
    // colour — and there is no control offering to resolve it.
    const notice = fixture.nativeElement.querySelector('[data-interrupt]');
    expect(notice?.getAttribute('data-interrupt')).toBe('staff_approval');
    expect(fixture.nativeElement.querySelector('button')).toBeNull();
  });

  it('treats done as the end of the turn and not as a resolution', () => {
    send();
    stream.events.next({ kind: 'done' });
    fixture.detectChanges();

    expect(state<boolean>('sending')).toBe(false);
    expect(state<string | null>('failure')).toBeNull();
    // Nothing on the surface claims the request was resolved.
    expect(fixture.nativeElement.textContent).not.toContain('resolved');
  });

  it('shows a failure as a failure rather than as an empty conversation', () => {
    // Spec FR-SURF-016: a failure MUST NOT be presented as an empty result.
    send();
    stream.events.next({ kind: 'error', title: 'The turn could not be completed.' });
    fixture.detectChanges();

    expect(state<string | null>('failure')).toBe('The turn could not be completed.');
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });
});
