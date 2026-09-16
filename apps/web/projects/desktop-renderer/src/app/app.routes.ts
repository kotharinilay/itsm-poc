import type { Routes } from '@angular/router';
import { CUSTOMER_FEATURE_ROUTES } from 'customer-features';

/**
 * Desktop renderer routes.
 *
 * The same customer feature routes the portal uses. Reuse rather than a parallel table is what
 * keeps the two customer surfaces from drifting (plan Stage 3).
 */
export const routes: Routes = [...CUSTOMER_FEATURE_ROUTES];
