import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService, objectId, type StaffRole } from 'platform-core';
import { App } from './app';

describe('Staff portal App', () => {
  const signInWith = (roles: readonly StaffRole[]): void => {
    TestBed.inject(AuthService).setSession({
      objectId: objectId('11111111-1111-1111-1111-111111111111'),
      displayName: 'Test Person',
      roles,
    });
  };

  const navLabels = (): readonly string[] => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    return Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.app-nav__list a'),
    ).map((anchor) => anchor.textContent?.trim() ?? '');
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('creates the app', () => {
    expect(TestBed.createComponent(App).componentInstance).toBeTruthy();
  });

  it('renders a skip link and a main landmark', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('a')?.getAttribute('href')).toBe('#main-content');
    expect(host.querySelector('main')?.id).toBe('main-content');
  });

  // FR-SURF-003: present only the modules the signed-in person's roles grant.
  it('shows a technician the technician modules', () => {
    signInWith(['technician']);
    expect(navLabels()).toEqual(['Approval queue', 'Live sessions', 'Reporting']);
  });

  // contracts/staff-api.md §Role model: administrator does not imply technician.
  it('does not let administrator see the technician modules', () => {
    signInWith(['administrator']);
    expect(navLabels()).toEqual(['Reporting']);
  });

  it('shows nothing to a person holding no staff role', () => {
    signInWith([]);
    expect(navLabels()).toEqual([]);
  });

  it('shows nothing before anyone signs in', () => {
    expect(navLabels()).toEqual([]);
  });

  it('is unaffected by the order roles are reported in', () => {
    signInWith(['administrator', 'technician']);
    const forward = navLabels();
    signInWith(['technician', 'administrator']);
    expect(navLabels()).toEqual(forward);
  });

  // FR-SURF-006: the staff portal must not provide any facility to start a session.
  it('offers no control that would originate a session', () => {
    signInWith(['technician', 'administrator']);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent?.toLowerCase() ?? '';
    for (const forbidden of ['new session', 'start session', 'new request', 'raise a request']) {
      expect(text)
        .withContext(`"${forbidden}" would originate a staff session`)
        .not.toContain(forbidden);
    }
  });
});
