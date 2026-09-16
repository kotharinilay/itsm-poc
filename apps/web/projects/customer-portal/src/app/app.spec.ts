import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('Customer portal App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('creates the app', () => {
    expect(TestBed.createComponent(App).componentInstance).toBeTruthy();
  });

  it('renders a skip link as the first focusable element (WCAG 2.4.1)', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const first = (fixture.nativeElement as HTMLElement).querySelector('a, button');
    expect(first?.getAttribute('href')).toBe('#main-content');
  });

  it('exposes a main landmark the skip link can reach', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const main = (fixture.nativeElement as HTMLElement).querySelector('main');
    expect(main?.id).toBe('main-content');
    expect(main?.getAttribute('tabindex')).toBe('-1');
  });

  it('labels its primary navigation', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const nav = (fixture.nativeElement as HTMLElement).querySelector('nav');
    expect(nav?.getAttribute('aria-label')).toBe('Primary');
  });

  it('reports the signed-out state honestly rather than assuming a session', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Not signed in');
  });
});
