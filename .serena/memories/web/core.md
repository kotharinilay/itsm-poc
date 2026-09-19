# Clients (`apps/web`, `apps/desktop`) — never security boundaries (constitution VII)

## Angular workspace `apps/web/projects/`
- Apps: `customer-portal`, `staff-portal`, `desktop-renderer` (loaded by Electron).
- Libs (build order): `design-system` (a11y, states, status) → `platform-core` (auth, API client, contracts, realtime — centralized) → `customer-features` (chat, feedback) / `staff-features`.
- `platform-core/no-authz.spec.ts` (`npm run test:architecture`) guards against authorization logic in the client.

## Electron `apps/desktop/`
- "Thin, hardened, decides nothing." `src/main/` main process, `src/preload/bridge.ts` (esbuild CJS bundle), renderer staged from web `desktop-renderer`.
- `tests/` vitest security suite; `build/scripts/verify-desktop-security-guard.sh`. Renderer origin + CSP nonce: ADR-0006. Endpoint script integrity: ADR-0004 (nothing actually executes in scaffold).
