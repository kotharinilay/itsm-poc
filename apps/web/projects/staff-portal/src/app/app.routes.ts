import type { Routes } from '@angular/router';
import { STAFF_FEATURE_ROUTES } from 'staff-features';

/**
 * Staff portal routes.
 *
 * Composed from `staff-features` only. Importing `customer-features` here would put a chat surface
 * on the staff portal and break spec FR-SURF-006 — an ESLint rule fails the build if anyone tries.
 */
export const routes: Routes = [...STAFF_FEATURE_ROUTES];
