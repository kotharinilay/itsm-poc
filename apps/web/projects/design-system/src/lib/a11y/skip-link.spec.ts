import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SkipLink } from './skip-link';

describe('SkipLink', () => {
  let fixture: ComponentFixture<SkipLink>;

  const anchor = (): HTMLAnchorElement =>
    fixture.nativeElement.querySelector('a') as HTMLAnchorElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SkipLink] }).compileComponents();
    fixture = TestBed.createComponent(SkipLink);
    fixture.detectChanges();
  });

  it('points at the main landmark by default', () => {
    expect(anchor().getAttribute('href')).toBe('#main-content');
  });

  it('carries a discernible accessible name', () => {
    expect(anchor().textContent?.trim()).toBe('Skip to main content');
  });

  it('honours an overridden target', () => {
    fixture.componentRef.setInput('targetId', 'queue');
    fixture.detectChanges();
    expect(anchor().getAttribute('href')).toBe('#queue');
  });
});
