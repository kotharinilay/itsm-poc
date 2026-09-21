import { Injectable, computed, inject, signal } from '@angular/core';
import { EMPTY, type Observable } from 'rxjs';
import type { StaffRole } from '../contracts/primitives';
import { ACCESS_TOKEN_PROVIDER, type AccessTokenProvider } from './access-token-provider';
import type { AuthSession, AuthStatus } from './auth-session';

/**
 * The one authentication integration point for all three surfaces.
 *
 * Centralised per FE-NG-4 (.claude/rules/23-angular.md): authentication and token handling are each
 * centralized rather than repeated." A surface asks this service who is signed in; it never talks
 * to an identity library, and it never handles a token.
 *
 * What this service does **not** do is decide anything. It reports what the identity provider said.
 * Authorization is the platform's, on every request, always (spec FR-SURF-004).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly tokenProvider = inject<AccessTokenProvider | null>(ACCESS_TOKEN_PROVIDER, {
    optional: true,
  });

  private readonly sessionSignal = signal<AuthSession | null>(null);
  private readonly statusSignal = signal<AuthStatus>('unknown');

  readonly session = this.sessionSignal.asReadonly();
  readonly status = this.statusSignal.asReadonly();

  readonly isSignedIn = computed(() => this.statusSignal() === 'signed-in');

  /**
   * Roles held, for presentation only.
   *
   * Read the name as a warning: anything gated on this is a menu, not a boundary.
   */
  readonly rolesForPresentation = computed<readonly StaffRole[]>(
    () => this.sessionSignal()?.roles ?? [],
  );

  /** Record the signed-in person. Called by the surface's identity integration, not by features. */
  setSession(session: AuthSession): void {
    this.sessionSignal.set(session);
    this.statusSignal.set('signed-in');
  }

  clearSession(): void {
    this.sessionSignal.set(null);
    this.statusSignal.set('signed-out');
  }

  /**
   * The current access token, or `null` when nobody is signed in or no provider is registered.
   *
   * The scaffold registers no provider, so this is `null` throughout Stage 3 — which is the honest
   * answer, not a stub pretending to be signed in.
   */
  accessToken(): Observable<string | null> {
    return this.tokenProvider?.getAccessToken() ?? EMPTY;
  }

  signIn(): Observable<void> {
    return this.tokenProvider?.signIn() ?? EMPTY;
  }

  signOut(): Observable<void> {
    this.clearSession();
    return this.tokenProvider?.signOut() ?? EMPTY;
  }
}
