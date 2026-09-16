import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { CursorPageQuery } from '../contracts/paging';
import { PLATFORM_API_CONFIG } from './platform-api.config';

/** A value that can appear in a query string. Objects and arrays are deliberately excluded. */
export type QueryValue = string | number | boolean | undefined;

/**
 * The single HTTP seam for both backends.
 *
 * Spec FR-SURF-017: a client addresses the platform through **one** gateway, and which backend
 * serves a given operation is not a client concern. That is why this class takes a path and not an
 * origin — there is no way to express "the other backend" through it, because there is no second
 * origin to express.
 *
 * Authentication, correlation and RFC 9457 handling are not here. They are interceptors, applied to
 * every request that leaves for the gateway whether it went through this class or not.
 */
@Injectable({ providedIn: 'root' })
export class PlatformApiClient {
  private readonly http = inject(HttpClient);
  private readonly config = inject(PLATFORM_API_CONFIG);

  get<T>(path: string, query: Readonly<Record<string, QueryValue>> = {}): Observable<T> {
    return this.http.get<T>(this.url(path), { params: toParams(query) });
  }

  post<TResponse, TBody = unknown>(path: string, body?: TBody): Observable<TResponse> {
    return this.http.post<TResponse>(this.url(path), body ?? null);
  }

  put<TResponse, TBody = unknown>(path: string, body?: TBody): Observable<TResponse> {
    return this.http.put<TResponse>(this.url(path), body ?? null);
  }

  delete<TResponse>(path: string): Observable<TResponse> {
    return this.http.delete<TResponse>(this.url(path));
  }

  /** Absolute URL for a platform path, against the one configured origin. */
  url(path: string): string {
    const origin = this.config.gatewayOrigin.replace(/\/+$/, '');
    const suffix = path.startsWith('/') ? path : `/${path}`;
    return `${origin}${suffix}`;
  }
}

/** Build query params, dropping absent values so an unset filter is never sent as "undefined". */
export function toParams(query: Readonly<Record<string, QueryValue>>): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      params = params.set(key, String(value));
    }
  }
  return params;
}

/**
 * Query params for a keyset-paged read.
 *
 * The cursor is carried verbatim: it is opaque to clients (contracts/README.md), so it is never
 * parsed, decoded or constructed here.
 */
export function pagingParams(query: CursorPageQuery): Record<string, QueryValue> {
  return {
    limit: query.limit,
    cursor: query.cursor,
    sort: query.sort,
  };
}
