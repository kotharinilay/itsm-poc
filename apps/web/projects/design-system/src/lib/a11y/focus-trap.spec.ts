import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FocusTrap } from './focus-trap';

@Component({
  imports: [FocusTrap],
  template: `
    <button type="button" id="outside">Outside</button>
    @if (open()) {
      <div [dsFocusTrap]="true">
        <button type="button" id="first">First</button>
        <button type="button" id="middle">Middle</button>
        <button type="button" id="last">Last</button>
      </div>
    }
  `,
})
class TrapHost {
  readonly open = signal(false);
}

describe('FocusTrap', () => {
  let fixture: ComponentFixture<TrapHost>;

  const byId = (id: string): HTMLElement => {
    const element = fixture.nativeElement.querySelector(`#${id}`);
    if (element === null) {
      throw new Error(`#${id} is not rendered`);
    }
    return element as HTMLElement;
  };

  const tab = (shiftKey: boolean): KeyboardEvent => {
    const event = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey,
      bubbles: true,
      cancelable: true,
    });
    (document.activeElement ?? fixture.nativeElement).dispatchEvent(event);
    fixture.detectChanges();
    return event;
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TrapHost] }).compileComponents();
    fixture = TestBed.createComponent(TrapHost);
    // Attached to the document so focus and visibility behave as they do in a real page.
    document.body.appendChild(fixture.nativeElement);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.nativeElement.remove();
  });

  it('moves focus to the first focusable element when armed', () => {
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    expect(document.activeElement).toBe(byId('first'));
  });

  it('wraps forward from the last element to the first', () => {
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    byId('last').focus();

    const event = tab(false);

    expect(event.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(byId('first'));
  });

  it('wraps backward from the first element to the last', () => {
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    byId('first').focus();

    const event = tab(true);

    expect(event.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(byId('last'));
  });

  it('leaves interior tab stops alone', () => {
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    byId('middle').focus();

    expect(tab(false).defaultPrevented).toBeFalse();
  });

  it('restores focus to the previously focused element when released', () => {
    byId('outside').focus();
    fixture.componentInstance.open.set(true);
    fixture.detectChanges();
    expect(document.activeElement).toBe(byId('first'));

    fixture.componentInstance.open.set(false);
    fixture.detectChanges();

    expect(document.activeElement).toBe(byId('outside'));
  });
});
