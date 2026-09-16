import { ComponentFixture, TestBed } from '@angular/core/testing';
import { STATE_DESCRIPTORS, type PresentationState } from './presentation-state';
import { StatusIndicator } from './status-indicator';

describe('StatusIndicator', () => {
  let fixture: ComponentFixture<StatusIndicator>;

  const render = (state: PresentationState, qualifier?: string): HTMLElement => {
    fixture.componentRef.setInput('state', state);
    if (qualifier !== undefined) {
      fixture.componentRef.setInput('qualifier', qualifier);
    }
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [StatusIndicator] }).compileComponents();
    fixture = TestBed.createComponent(StatusIndicator);
  });

  // FR-SURF-013 — the states the requirement names by hand.
  for (const state of ['suspended', 'pending', 'expired'] as const) {
    it(`conveys "${state}" by text as well as colour`, () => {
      const host = render(state);
      const label = host.querySelector('.ds-status__label');
      expect(label?.textContent?.trim()).toBe(STATE_DESCRIPTORS[state].label);
    });

    it(`conveys "${state}" by a glyph as well as colour`, () => {
      const host = render(state);
      expect(host.querySelector('.ds-status__glyph')?.textContent?.trim()).toBe(
        STATE_DESCRIPTORS[state].glyph,
      );
    });
  }

  it('hides the decorative glyph from assistive technology', () => {
    const host = render('suspended');
    expect(host.querySelector('.ds-status__glyph')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('gives every state a distinct glyph, so colour is never the only difference', () => {
    const glyphs = Object.values(STATE_DESCRIPTORS).map((descriptor) => descriptor.glyph);
    expect(new Set(glyphs).size).toBe(glyphs.length);
  });

  it('appends a qualifier to the accessible name', () => {
    const host = render('pending', 'awaiting your approval');
    expect(host.querySelector('.ds-status__label')?.textContent?.trim()).toBe(
      'Pending — awaiting your approval',
    );
  });
});
