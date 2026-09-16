/**
 * Tests for the desktop renderer shell.
 *
 * The shell is scaffold, so these assert structure rather than behaviour: that it renders, that it
 * reports host status without a host present, and — the one that matters — that it gates nothing
 * on a client-side decision (spec FR-SURF-004).
 */

import { TestBed } from '@angular/core/testing';

import { App } from './app';
import { BRIDGE_GLOBAL_KEY } from './desktop/desktop-bridge.types';

describe('App', () => {
  beforeEach(async () => {
    delete (globalThis as Record<string, unknown>)[BRIDGE_GLOBAL_KEY];
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
  });

  it('creates the shell', () => {
    expect(TestBed.createComponent(App).componentInstance).toBeTruthy();
  });

  it('renders the application title', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Synthia');
  });

  it('reports that there is no desktop host when running in a browser', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Browser (no desktop host)');
  });

  it('provides a main landmark and a skip link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('main#main-content')).not.toBeNull();
    expect(compiled.querySelector('a.skip-link')?.getAttribute('href')).toBe('#main-content');
  });

  it('renders no element gated on a client-side authorization decision', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const markup = (fixture.nativeElement as HTMLElement).innerHTML.toLowerCase();
    for (const word of ['role=', 'permission', 'approval', 'authoriz', 'tenant']) {
      // `role=` would be an ARIA role in markup; the shell uses native landmarks instead, so its
      // absence also keeps this assertion unambiguous.
      expect(markup).not.toContain(word);
    }
  });
});
