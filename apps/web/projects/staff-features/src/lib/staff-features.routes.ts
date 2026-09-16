import type { Routes } from '@angular/router';
import { canMatchForPresentation } from 'platform-core';

/**
 * Staff feature routes.
 *
 * ## There is no session-origination route, and there must never be one
 *
 * Spec FR-SURF-006: the staff portal MUST NOT provide any facility to start a chat session or raise
 * a support request. It exists for staff to work on other people's sessions, not to originate their
 * own. A staff member who needs help uses a customer surface, where they are an end user like
 * anybody else and their staff roles confer nothing (FR-SURF-007, FR-SURF-008).
 *
 * The absence is asserted by `staff-features.routes.spec.ts`, and reinforced by an ESLint rule that
 * stops `staff-portal` importing `customer-features` — which is how this rule would otherwise get
 * broken by accident rather than by intent.
 *
 * ## The guards below are convenience, not security
 *
 * `canMatchForPresentation` hides a route the platform would refuse anyway. It is not a security
 * boundary: the person holds the browser. Every request from every one of these surfaces is
 * authorized by the platform from scratch (FR-SURF-004). Deleting every guard here would change
 * nothing about what anyone can actually do.
 */
export const STAFF_FEATURE_ROUTES: Routes = [
  {
    path: 'queue',
    title: 'Approval queue',
    canMatch: [canMatchForPresentation(['technician'])],
    loadComponent: () => import('./queue/queue-shell').then((m) => m.QueueShell),
  },
  {
    path: 'sessions',
    title: 'Live sessions',
    canMatch: [canMatchForPresentation(['technician'])],
    loadComponent: () => import('./take-over/take-over-shell').then((m) => m.TakeOverShell),
  },
  {
    path: 'reporting',
    title: 'Reporting',
    // `technician` and `administrator` are independent: neither implies the other, so both are
    // listed rather than one being assumed to cover the other.
    canMatch: [canMatchForPresentation(['technician', 'administrator'])],
    loadComponent: () => import('./reporting/reporting-shell').then((m) => m.ReportingShell),
  },
  { path: '', pathMatch: 'full', redirectTo: 'queue' },
];

/**
 * Path segments that would constitute session origination on a staff surface.
 *
 * Kept next to the route table so the test and the rule cannot drift apart.
 */
export const FORBIDDEN_STAFF_ROUTE_SEGMENTS: readonly string[] = [
  'new-session',
  'start-session',
  'new-request',
  'raise-request',
  'new-chat',
  'start-chat',
  'compose',
];
