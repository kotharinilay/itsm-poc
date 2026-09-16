import type { Routes } from '@angular/router';

/**
 * Customer feature routes, lazily loaded by each customer surface.
 *
 * Shared by the customer portal **and** the desktop renderer, which is the point of the library:
 * the desktop client reuses these features and adds only its bridge, rather than growing a second
 * copy that drifts (plan Stage 3).
 *
 * There is no guard here. Every person on a customer surface is an end user, and no staff role
 * check is applied on a customer surface (spec FR-SURF-008) — so there is nothing for a guard to
 * check.
 */
export const CUSTOMER_FEATURE_ROUTES: Routes = [
  {
    path: 'sessions',
    title: 'Your sessions',
    loadComponent: () => import('./session/session-shell').then((m) => m.SessionShell),
  },
  {
    path: 'sessions/:sessionId',
    title: 'Conversation',
    loadComponent: () => import('./chat/chat-shell').then((m) => m.ChatShell),
  },
  {
    path: 'sessions/:sessionId/consent',
    title: 'Permission needed',
    loadComponent: () => import('./consent/consent-shell').then((m) => m.ConsentShell),
  },
  {
    path: 'sessions/:sessionId/support',
    title: 'Support',
    loadComponent: () => import('./handoff/handoff-shell').then((m) => m.HandoffShell),
  },
  { path: '', pathMatch: 'full', redirectTo: 'sessions' },
];
