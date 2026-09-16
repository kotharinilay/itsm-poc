import { TestBed } from '@angular/core/testing';
import { LiveAnnouncer } from './live-announcer';

describe('LiveAnnouncer', () => {
  let announcer: LiveAnnouncer;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    announcer = TestBed.inject(LiveAnnouncer);
  });

  afterEach(() => {
    announcer.ngOnDestroy();
  });

  const politeRegion = (): HTMLElement | null =>
    document.querySelector('[aria-live="polite"]') as HTMLElement | null;

  it('creates a polite live region on first announcement', () => {
    announcer.announce('Loading your sessions');
    expect(politeRegion()?.textContent).toBe('Loading your sessions');
  });

  it('creates an assertive region with role alert', () => {
    announcer.announce('Your session expired', 'assertive');
    const region = document.querySelector('[aria-live="assertive"]');
    expect(region?.getAttribute('role')).toBe('alert');
  });

  it('ignores an empty announcement', () => {
    announcer.announce('   ');
    expect(politeRegion()).toBeNull();
  });

  // FR-SURF-011: a growing response is never read back from the beginning.
  it('announces only the text not already announced', () => {
    expect(announcer.announceDelta('s1', 'Hello')).toBe('Hello');
    expect(announcer.announceDelta('s1', 'Hello there')).toBe(' there');
    expect(announcer.announceDelta('s1', 'Hello there friend')).toBe(' friend');
  });

  it('writes only the delta into the live region', () => {
    announcer.announceDelta('s1', 'Hello');
    announcer.announceDelta('s1', 'Hello there');
    expect(politeRegion()?.textContent).toBe('there');
  });

  it('announces nothing when the text has not advanced', () => {
    announcer.announceDelta('s1', 'Hello');
    expect(announcer.announceDelta('s1', 'Hello')).toBe('');
  });

  it('tracks streams independently', () => {
    announcer.announceDelta('a', 'One');
    announcer.announceDelta('b', 'Two');
    expect(announcer.announceDelta('a', 'One more')).toBe(' more');
  });

  it('re-announces in full when the text is rewritten rather than appended', () => {
    announcer.announceDelta('s1', 'Hello there');
    expect(announcer.announceDelta('s1', 'Sorry, something went wrong')).toBe(
      'Sorry, something went wrong',
    );
  });

  it('starts clean after the stream ends', () => {
    announcer.announceDelta('s1', 'Hello');
    announcer.endStream('s1');
    expect(announcer.announceDelta('s1', 'Hello')).toBe('Hello');
  });

  it('removes its regions on destroy', () => {
    announcer.announce('x');
    announcer.ngOnDestroy();
    expect(politeRegion()).toBeNull();
  });
});
