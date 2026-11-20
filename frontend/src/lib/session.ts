import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";
import {
  BackendUnavailable,
  MOCK_PREFIX,
  SESSION_COOKIE,
  backendRequest,
  type Api,
} from "@/lib/api/backendClient";

export type Role = "lawyer" | "client";
export type Session = { role: Role; user: Api["UserResponse"] | null };
export type LoginState =
  | { status: "NOT_CONFIGURED" }
  | { status: "INVALID" }
  | { status: "UNAVAILABLE" }
  | null;

const SESSION_MAX_AGE = 60 * 60 * 8;

function cookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  };
}

export function isMockAuthEnabled() {
  return process.env.NODE_ENV !== "production" && process.env.MOCK_AUTH === "true";
}

function roleFor(user: Api["UserResponse"]): Role {
  return user.role === "client" ? "client" : "lawyer";
}

/** The signed-in user. The backend decides the role; mock sign-in is development only. */
export const getSession = cache(async (): Promise<Session | null> => {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value) return null;

  if (value.startsWith(MOCK_PREFIX)) {
    if (!isMockAuthEnabled()) return null;
    const role = value.slice(MOCK_PREFIX.length);
    return role === "lawyer" || role === "client" ? { role, user: null } : null;
  }

  try {
    const response = await backendRequest("/api/v1/me", { token: value });
    if (!response.ok) return null;
    const user = (await response.json()) as Api["UserResponse"];
    return { role: roleFor(user), user };
  } catch (error) {
    if (error instanceof BackendUnavailable) return null;
    throw error;
  }
});

export async function setMockSession(role: Role): Promise<boolean> {
  if (!isMockAuthEnabled()) return false;

  const store = await cookies();
  store.set(SESSION_COOKIE, `${MOCK_PREFIX}${role}`, cookieOptions());
  return true;
}

function tokenFrom(response: Response): string | null {
  for (const header of response.headers.getSetCookie()) {
    const [pair] = header.split(";");
    const index = pair.indexOf("=");
    if (pair.slice(0, index).trim() === SESSION_COOKIE) {
      return pair.slice(index + 1).trim() || null;
    }
  }
  return null;
}

/** Sign in against the backend and keep its session token in our httpOnly cookie. */
export async function signInWithBackend(
  email: string,
  password: string,
): Promise<{ role: Role } | LoginState> {
  let response: Response;
  try {
    response = await backendRequest("/api/v1/auth/login", {
      method: "POST",
      json: { email, password },
    });
  } catch (error) {
    if (error instanceof BackendUnavailable) return { status: "UNAVAILABLE" };
    throw error;
  }
  if (!response.ok) return { status: "INVALID" };

  const token = tokenFrom(response);
  if (!token) return { status: "INVALID" };
  const user = (await response.json()) as Api["UserResponse"];

  (await cookies()).set(SESSION_COOKIE, token, cookieOptions());
  return { role: roleFor(user) };
}

export async function clearSession() {
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  if (value && !value.startsWith(MOCK_PREFIX)) {
    try {
      await backendRequest("/api/v1/auth/logout", { method: "POST", token: value });
    } catch {
      // Signing out locally still clears the cookie.
    }
  }
  store.set(SESSION_COOKIE, "", { ...cookieOptions(), maxAge: 0 });
}
