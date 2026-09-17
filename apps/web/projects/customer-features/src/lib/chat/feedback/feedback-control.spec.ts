import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PLATFORM_API_CONFIG, messageId } from 'platform-core';
import { FeedbackControl } from './feedback-control';

/**
 * The feedback control: keyboard-operable, announced, and with its state visible (`SC-SESS-003`).
 *
 * The assertions worth having here are the ones a plausible-looking implementation fails: that the
 * controls are real buttons rather than clickable `div`s, that the recorded state is conveyed by
 * something other than colour, and that a failed write reverts rather than leaving the user looking
 * at a signal the platform does not hold.
 */
@Component({
  standalone: true,
  imports: [FeedbackControl],
  template: `<cf-feedback-control [messageId]="id" />`,
})
class Host {
  protected readonly id = messageId('11111111-1111-1111-1111-111111111111');
}

describe('FeedbackControl', () => {
  let fixture: ComponentFixture<Host>;
  let http: HttpTestingController;

  const buttons = (): HTMLButtonElement[] =>
    Array.from(fixture.nativeElement.querySelectorAll('button'));

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Host],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
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

    fixture = TestBed.createComponent(Host);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('is operable from the keyboard because the controls are buttons', () => {
    // Real `<button>` elements: focus, Enter and Space come from the platform. A
    // `<div role="button">` would need tabindex and two key handlers — three chances to be wrong.
    expect(buttons().length).toBe(2);
    expect(buttons().every((button) => button.type === 'button')).toBe(true);
  });

  it('exposes the two signals as a labelled group', () => {
    const group = fixture.nativeElement.querySelector('[role="group"]');
    expect(group?.getAttribute('aria-label')).toBe('Was this helpful?');
  });

  it('starts with neither signal pressed', () => {
    expect(buttons().every((button) => button.getAttribute('aria-pressed') === 'false')).toBe(true);
  });

  it('records a signal and shows the state to assistive technology and to the eye', () => {
    buttons()[0]!.click();
    fixture.detectChanges();

    // Announced state...
    expect(buttons()[0]!.getAttribute('aria-pressed')).toBe('true');
    // ...and visible state, by something other than colour.
    expect(buttons()[0]!.getAttribute('data-state')).toBe('on');
    expect(buttons()[1]!.getAttribute('data-state')).toBe('off');

    const request = http.expectOne(
      'https://api.test.example/api/customer/v1/messages/11111111-1111-1111-1111-111111111111/feedback',
    );
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ signal: 'positive' });
    request.flush(null);
  });

  it('replaces rather than accumulates when the other signal is chosen', () => {
    buttons()[0]!.click();
    fixture.detectChanges();
    http.expectOne(() => true).flush(null);

    buttons()[1]!.click();
    fixture.detectChanges();

    expect(buttons()[0]!.getAttribute('aria-pressed')).toBe('false');
    expect(buttons()[1]!.getAttribute('aria-pressed')).toBe('true');

    const request = http.expectOne(() => true);
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ signal: 'negative' });
    request.flush(null);
  });

  it('withdraws when the pressed signal is chosen again', () => {
    buttons()[0]!.click();
    fixture.detectChanges();
    http.expectOne(() => true).flush(null);

    buttons()[0]!.click();
    fixture.detectChanges();

    expect(buttons()[0]!.getAttribute('aria-pressed')).toBe('false');

    const request = http.expectOne(() => true);
    expect(request.request.method).toBe('DELETE');
    request.flush(null);
  });

  it('reverts and says so when the write does not reach the platform', () => {
    // Keeping the optimistic state would show a signal the platform does not hold — a small lie
    // the user has no way to detect.
    buttons()[0]!.click();
    fixture.detectChanges();

    http.expectOne(() => true).flush(null, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    expect(buttons()[0]!.getAttribute('aria-pressed')).toBe('false');
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });
});
