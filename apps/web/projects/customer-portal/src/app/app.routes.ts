import type { Routes } from '@angular/router';
import { CUSTOMER_FEATURE_ROUTES } from 'customer-features';

/**
 * Customer portal routes.
 *
 * The surface composes the shared customer features rather than redefining them, so the desktop
 * renderer and this portal cannot drift apart (plan Stage 3).
 */
export const routes: Routes = [...CUSTOMER_FEATURE_ROUTES];
