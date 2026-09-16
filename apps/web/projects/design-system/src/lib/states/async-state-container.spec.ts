import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { type AsyncState, empty, failed, idle, loading, partial, ready } from './async-state';
import { AsyncStateContainer } from './async-state-container';
import { presentableFailure } from './presentable-failure';

@Component({
  imports: [AsyncStateContainer],
  template: `
    <ds-async-state-container [state]="state()">
      <p id="projected">Projected content</p>
    </ds-async-state-container>
  `,
})
class ContainerHost {
  readonly state = signal<AsyncState<readonly string[]>>(idle());
}

describe('AsyncStateContainer', () => {
  let fixture: ComponentFixture<ContainerHost>;

  const render = (state: AsyncState<readonly string[]>): HTMLElement => {
    fixture.componentInstance.state.set(state);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  };

  const failure = presentableFailure('server', 'The queue is unavailable');

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ContainerHost] }).compileComponents();
    fixture = TestBed.createComponent(ContainerHost);
  });

  it('renders nothing for idle', () => {
    const host = render(idle());
    expect(host.querySelector('ds-loading-state')).toBeNull();
    expect(host.querySelector('ds-empty-state')).toBeNull();
    expect(host.querySelector('ds-partial-failure-state')).toBeNull();
  });

  it('renders a busy status for loading', () => {
    const host = render(loading());
    expect(host.querySelector('ds-loading-state [role="status"]')).not.toBeNull();
  });

  it('renders the empty state for empty', () => {
    const host = render(empty());
    expect(host.querySelector('ds-empty-state')).not.toBeNull();
  });

  // FR-SURF-016 — the rule this component exists to make structural.
  it('never renders the empty state for a failure', () => {
    const host = render(failed(failure));
    expect(host.querySelector('ds-empty-state')).toBeNull();
    expect(host.querySelector('ds-partial-failure-state')).not.toBeNull();
  });

  it('announces a failure through an alert', () => {
    const host = render(failed(failure));
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('The queue is unavailable');
  });

  it('shows both the data and the failure for a partial read', () => {
    const host = render(partial(['a'], failure));
    expect(host.querySelector('#projected')).not.toBeNull();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain(
      'Some information could not be loaded',
    );
  });

  it('projects content for ready without any state chrome', () => {
    const host = render(ready(['a']));
    expect(host.querySelector('#projected')).not.toBeNull();
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });

  it('offers a retry for a retryable failure', () => {
    const host = render(failed(failure));
    expect(host.querySelector('.ds-failure__retry')).not.toBeNull();
  });

  it('does not offer a retry for a decision the platform already made', () => {
    const host = render(failed(presentableFailure('forbidden', 'Not allowed')));
    expect(host.querySelector('.ds-failure__retry')).toBeNull();
  });
});
