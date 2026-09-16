import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, StatusIndicator, idle } from 'design-system';
import { RealtimeService, StaffApiClient, type ApprovalQueueEntry } from 'platform-core';

/**
 * Approval queue shell.
 *
 * Structural shell only — no approval behaviour is implemented.
 *
 * Three rules shape it, and each is the platform's rule rather than this component's:
 *
 *  - The queue is **read** from the monolith; a verdict is **written** to RagCore. Both go through
 *    the one gateway, so the split is not a client concern (contracts/staff-api.md).
 *  - An `approval.decided` notification refreshes this view. It is not a verdict and does not carry
 *    one; the verdict is an authenticated request that identifies the decider (FR-SURF-018).
 *  - The queue discloses the **full** command. It is never abbreviated, because the approver is
 *    being asked to take responsibility for exactly what will run.
 */
@Component({
  selector: 'sf-queue-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer, StatusIndicator],
  templateUrl: './queue-shell.html',
  styleUrl: './queue-shell.css',
})
export class QueueShell {
  protected readonly api = inject(StaffApiClient);
  protected readonly realtime = inject(RealtimeService);

  protected readonly queue = signal<AsyncState<readonly ApprovalQueueEntry[]>>(idle());
}
