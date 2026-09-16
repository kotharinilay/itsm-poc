import { TestBed } from '@angular/core/testing';
import { DesktopBridgeService } from './desktop-bridge.service';

describe('DesktopBridgeService', () => {
  let service: DesktopBridgeService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DesktopBridgeService);
  });

  it('reports the host as unavailable in a browser', () => {
    expect(service.isAvailable()).toBeFalse();
  });

  it('reports no platform or host version without a host', () => {
    expect(service.platform()).toBeNull();
    expect(service.hostVersion()).toBeNull();
  });

  // Failing loudly beats pretending the work ran.
  it('rejects an execution request when the host is absent', async () => {
    await expectAsync(
      service.executeVerifiedInstruction({ workItemId: 'w1', contentHash: 'h1' }),
    ).toBeRejectedWithError(/bridge is not available/);
  });
});
