import { InjectionToken } from '@angular/core';
import type { Observable } from 'rxjs';

/**
 * The seam between the application and whichever identity library acquires tokens.
 *
 * Declared as a port rather than depending on MSAL directly so the scaffold has exactly one place
 * where authentication is integrated. Swapping the library, or stubbing it in a test, replaces this
 * provider and touches nothing else.
 *
 * The scaffold ships no implementation on purpose — Stage 3 has no identity plane behind it yet.
 */
export interface AccessTokenProvider {
  /**
   * An access token for the platform audience, or `null` when nobody is signed in.
   *
   * The token is passed to the gateway and never inspected here. A client that parses a token is
   * one step from making a decision with it, and spec FR-SURF-004 forbids that.
   */
  getAccessToken(): Observable<string | null>;

  /** Begin an interactive sign-in. Resolves when the redirect or popup flow has been started. */
  signIn(): Observable<void>;

  signOut(): Observable<void>;
}

export const ACCESS_TOKEN_PROVIDER = new InjectionToken<AccessTokenProvider>(
  'ACCESS_TOKEN_PROVIDER',
);
