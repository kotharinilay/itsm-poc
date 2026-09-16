import {
  empty,
  failed,
  failureOf,
  hasFailure,
  idle,
  isPending,
  loading,
  partial,
  ready,
  readyOrEmpty,
  valueOf,
} from './async-state';
import { presentableFailure } from './presentable-failure';

describe('AsyncState', () => {
  const failure = presentableFailure('server', 'The queue is unavailable');

  it('distinguishes an empty result from a failed one', () => {
    // FR-SURF-016: a failure MUST NOT be presented as an empty result.
    expect(empty().status).toBe('empty');
    expect(failed(failure).status).toBe('failed');
    expect(empty().status).not.toBe(failed(failure).status);
  });

  it('routes a zero-length successful read to empty, never to failed', () => {
    expect(readyOrEmpty([]).status).toBe('empty');
  });

  it('routes a populated successful read to ready', () => {
    const state = readyOrEmpty(['a']);
    expect(state.status).toBe('ready');
    expect(valueOf(state)).toEqual(['a']);
  });

  it('treats a partial read as carrying a failure', () => {
    expect(hasFailure(partial(['a'], failure))).toBeTrue();
    expect(hasFailure(failed(failure))).toBeTrue();
  });

  it('does not treat empty or ready as a failure', () => {
    expect(hasFailure(empty())).toBeFalse();
    expect(hasFailure(ready('x'))).toBeFalse();
    expect(hasFailure(idle())).toBeFalse();
  });

  it('exposes both the value and the failure of a partial read', () => {
    const state = partial(['a'], failure);
    expect(valueOf(state)).toEqual(['a']);
    expect(failureOf(state)).toBe(failure);
  });

  it('reports only loading as pending', () => {
    expect(isPending(loading())).toBeTrue();
    expect(isPending(idle())).toBeFalse();
    expect(isPending(ready('x'))).toBeFalse();
  });

  it('has no failure on a successful read', () => {
    expect(failureOf(ready('x'))).toBeUndefined();
  });
});

describe('presentableFailure', () => {
  it('marks transport failures retryable', () => {
    expect(presentableFailure('network', 'Offline').retryable).toBeTrue();
    expect(presentableFailure('timeout', 'Too slow').retryable).toBeTrue();
    expect(presentableFailure('server', 'Broken').retryable).toBeTrue();
  });

  it('does not invite a retry of a decision the platform already made', () => {
    expect(presentableFailure('forbidden', 'Not allowed').retryable).toBeFalse();
    expect(presentableFailure('not-found', 'Gone').retryable).toBeFalse();
  });

  it('omits absent optional fields rather than setting them undefined', () => {
    expect('detail' in presentableFailure('server', 'Broken')).toBeFalse();
  });

  it('carries a correlation id when one is supplied', () => {
    expect(presentableFailure('server', 'Broken', { correlationId: 'abc' }).correlationId).toBe(
      'abc',
    );
  });
});
