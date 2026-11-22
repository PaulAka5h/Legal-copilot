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
/**
 * passwordChangeRequired: the backend refuses everything but password change
 * and logout until the user replaces a lawyer-set temporary password. Only
 * lawyer-created client logins carry it, so such a session is a client one.
 */
export type Session = {
  role: Role;
  user: Api["UserResponse"] | null;
  passwordChangeRequired?: boolean;
};
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

export async function hasSessionCookie(): Promise<boolean> {
  return Boolean((await cookies()).get(SESSION_COOKIE)?.value);
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
    if (response.status === 403 && (await isPasswordChangeRequired(response))) {
      return { role: "client", user: null, passwordChangeRequired: true };
    }
    if (!response.ok) return null;
    const user = (await response.json()) as Api["UserResponse"];
    return { role: roleFor(user), user };
  } catch (error) {
    if (error instanceof BackendUnavailable) return null;
    throw error;
  }
});

export const PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED";

async function isPasswordChangeRequired(response: Response): Promise<boolean> {
  try {
    const problem = (await response.json()) as { detail?: unknown };
    return typeof problem.detail === "string" && problem.detail.startsWith(PASSWORD_CHANGE_REQUIRED);
  } catch {
    return false;
  }
}

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

/**
 * Sign in against the backend for one portal and keep its session token in our
 * httpOnly cookie. The backend refuses an account of another role with the same
 * generic error as a wrong password and creates no session.
 */
export async function signInWithBackend(
  email: string,
  password: string,
  expectedRole: Role,
): Promise<{ role: Role; mustChangePassword: boolean } | LoginState> {
  let response: Response;
  try {
    response = await backendRequest("/api/v1/auth/login", {
      method: "POST",
      json: { email, password, expected_role: expectedRole } satisfies Api["LoginRequest"],
    });
  } catch (error) {
    if (error instanceof BackendUnavailable) return { status: "UNAVAILABLE" };
    throw error;
  }
  if (!response.ok) return { status: "INVALID" };

  const token = tokenFrom(response);
  if (!token) return { status: "INVALID" };
  const user = (await response.json()) as Api["UserResponse"];
  // Defence in depth: never keep a session for the other portal's role.
  if (roleFor(user) !== expectedRole) return { status: "INVALID" };

  (await cookies()).set(SESSION_COOKIE, token, cookieOptions());
  return { role: roleFor(user), mustChangePassword: Boolean(user.must_change_password) };
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

/**
 * Where a signed-in user should land from a login page, or null to show the
 * login form. Login pages only redirect when that page can load: a session
 * whose dashboard data fails would otherwise bounce the user back and forth.
 */
export async function readyDestination(session: Session | null): Promise<string | null> {
  if (!session) return null;
  if (session.passwordChangeRequired) return "/client/set-password";
  const dashboard = session.role === "client" ? "/client/dashboard" : "/lawyer/dashboard";
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token || token.startsWith(MOCK_PREFIX)) return dashboard;

  const probe = session.role === "client" ? "/api/v1/client/cases" : "/api/v1/lawyer/dashboard/overview";
  try {
    return (await backendRequest(probe, { token })).ok ? dashboard : null;
  } catch (error) {
    if (error instanceof BackendUnavailable) return null;
    throw error;
  }
}
