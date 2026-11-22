import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import type { components } from "@/lib/api/schema";

/**
 * Server-side client for the FastAPI backend. Types come from the backend
 * OpenAPI schema (`npm run gen:api`). Components never call this directly;
 * lib/api/lawyer.ts and lib/api/client.ts adapt responses to UI shapes.
 */

export type Api = components["schemas"];

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";
// The backend's CSRF check compares Origin with its APP_ORIGIN setting.
const APP_ORIGIN = process.env.APP_ORIGIN ?? "http://localhost:3000";
const TIMEOUT_MS = Number(process.env.BACKEND_TIMEOUT_MS ?? 120_000);

export const SESSION_COOKIE = "lc_session";
export const MOCK_PREFIX = "mock.";

/** The backend could not be reached (network error or timeout). */
export class BackendUnavailable extends Error {
  constructor() {
    super("Backend is unreachable.");
  }
}

/** The backend answered with an error status. */
export class BackendError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`Backend returned ${status}.`);
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type RequestOptions = {
  method?: Method;
  json?: unknown;
  form?: FormData;
  token?: string;
};

// Per-request flag: set when any data on the page came from the demo fallback.
const demoState = cache(() => ({ used: false }));

export function markDemoData() {
  demoState().used = true;
}

export function usedDemoData() {
  return demoState().used;
}

/** The backend session token from our cookie, or null for no or mock sessions. */
export async function sessionToken(): Promise<string | null> {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value || value.startsWith(MOCK_PREFIX)) return null;
  return value;
}

/** Raw request; returns the Response so callers can read Set-Cookie. */
export async function backendRequest(
  path: string,
  { method = "GET", json, form, token }: RequestOptions = {},
): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers.Origin = APP_ORIGIN;
  if (json !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Cookie = `${SESSION_COOKIE}=${token}`;

  try {
    return await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new BackendUnavailable();
  }
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const { detail } = body as { detail: unknown };
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    // Not JSON; fall through.
  }
  return response.statusText;
}

/**
 * Authenticated JSON call as the signed-in user. Throws BackendUnavailable when
 * there is no real session (mock sign-in) or the backend cannot be reached.
 */
export async function backend<T>(
  path: string,
  options: Omit<RequestOptions, "token"> = {},
): Promise<T> {
  const token = await sessionToken();
  if (!token) throw new BackendUnavailable();

  const response = await backendRequest(path, { ...options, token });
  if (response.status === 401) redirect("/");
  if (!response.ok) {
    throw new BackendError(response.status, await errorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Like backend(), but a 404 becomes null. */
export async function backendOrNull<T>(
  path: string,
  options: Omit<RequestOptions, "token"> = {},
): Promise<T | null> {
  try {
    return await backend<T>(path, options);
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) return null;
    throw error;
  }
}

/**
 * Run the real call; on BackendUnavailable use the demo fallback and mark the
 * page as showing demo data. Other errors propagate.
 */
export async function withDemoFallback<T>(
  real: () => Promise<T>,
  demo: () => T | Promise<T>,
): Promise<T> {
  try {
    return await real();
  } catch (error) {
    if (!(error instanceof BackendUnavailable)) throw error;
    markDemoData();
    return demo();
  }
}

export function caseUrl(caseId: string, suffix = "") {
  return `/api/v1/lawyer/cases/${encodeURIComponent(caseId)}${suffix}`;
}
