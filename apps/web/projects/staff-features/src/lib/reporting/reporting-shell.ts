import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { AsyncStateContainer, type AsyncState, idle } from 'design-system';
import { StaffApiClient, type AuditEntry } from 'platform-core';

/**
 * Reporting shell — audit search and the platform dashboard.
 *
 * Structural shell only — no reporting behaviour is implemented.
 *
 * The dashboard accepts `administrator` and audit accepts `technician`, and the two do not imply
 * each other (contracts/staff-api.md §Role model). The route table hides what a person's roles do
 * not reach, for convenience; the platform refuses it regardless.
 */
@Component({
  selector: 'sf-reporting-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncStateContainer],
  templateUrl: './reporting-shell.html',
  styleUrl: './reporting-shell.css',
})
export class ReportingShell {
  protected readonly api = inject(StaffApiClient);
  protected readonly audit = signal<AsyncState<readonly AuditEntry[]>>(idle());
}
