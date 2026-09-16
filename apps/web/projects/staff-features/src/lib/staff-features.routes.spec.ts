import type { Route } from '@angular/router';
import { FORBIDDEN_STAFF_ROUTE_SEGMENTS, STAFF_FEATURE_ROUTES } from './staff-features.routes';

function flatten(routes: readonly Route[], prefix = ''): readonly string[] {
  return routes.flatMap((route) => {
    const path = [prefix, route.path ?? ''].filter((segment) => segment.length > 0).join('/');
    return [path, ...flatten(route.children ?? [], path)];
  });
}

describe('staff feature routes', () => {
  const paths = flatten(STAFF_FEATURE_ROUTES);

  it('exposes the three staff surfaces', () => {
    expect(paths).toContain('queue');
    expect(paths).toContain('sessions');
    expect(paths).toContain('reporting');
  });

  // FR-SURF-006 — the staff portal exists to work on other people's sessions, not to start one.
  it('exposes no session-origination route', () => {
    for (const forbidden of FORBIDDEN_STAFF_ROUTE_SEGMENTS) {
      const offenders = paths.filter((path) => path.includes(forbidden));
      expect(offenders)
        .withContext(`"${forbidden}" would let staff originate their own session`)
        .toEqual([]);
    }
  });

  it('exposes no redirect that lands on an origination path', () => {
    const redirects = STAFF_FEATURE_ROUTES.map((route) => route.redirectTo).filter(
      (target): target is string => typeof target === 'string',
    );
    for (const target of redirects) {
      for (const forbidden of FORBIDDEN_STAFF_ROUTE_SEGMENTS) {
        expect(target).not.toContain(forbidden);
      }
    }
  });

  it('gates every feature route, so no menu item promises what the platform refuses', () => {
    const featureRoutes = STAFF_FEATURE_ROUTES.filter((route) => route.loadComponent !== undefined);
    expect(featureRoutes.length).toBeGreaterThan(0);
    for (const route of featureRoutes) {
      expect(route.canMatch)
        .withContext(`route "${route.path}" has no presentation gate`)
        .toBeDefined();
    }
  });
});
