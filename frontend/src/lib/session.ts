import "server-only";

import { cookies } from "next/headers";
import { getCurrentUser, type CurrentUser } from "@/lib/api/backendClient";

export type Role = "lawyer" | "client";
export type Session = CurrentUser & { role: Role };
export type LoginState =
  | { status: "invalid"; message: string; mfa?: boolean }
  | { status: "rate_limited"; message: string }
  | { status: "NOT_CONFIGURED" }
  | null;

const SESSION_COOKIE = "lc_session";
const MOCK_PREFIX = "mock.";
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

export async function getSession(): Promise<Session | null> {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value) return null;

  // Reject mock cookies when mock auth is disabled
  if (value.startsWith(MOCK_PREFIX)) {
    if (isMockAuthEnabled()) {
      const role = value.slice(MOCK_PREFIX.length);
      return role === "lawyer" || role === "client"
        ? {
            id: `mock-${role}`,
            email: "mock@example.invalid",
            role,
            full_name: "SAMPLE_DATA_NOT_REAL_LAW",
            preferred_language: "en",
          }
        : null;
    }
    // Mock cookie present but mock auth disabled - treat as invalid
    return null;
  }

  if (isMockAuthEnabled()) {
    // Real cookie but mock auth enabled - treat as invalid for safety
    return null;
  }

  const user = await getCurrentUser();
  if (!user) return null;
  const role = user.role;
  if (role !== "lawyer" && role !== "client") return null;
  return user as Session;
}

export async function setMockSession(role: Role): Promise<boolean> {
  if (!isMockAuthEnabled()) return false;

  const store = await cookies();
  store.set(SESSION_COOKIE, `${MOCK_PREFIX}${role}`, cookieOptions());
  return true;
}

export async function clearSession() {
  const store = await cookies();
  store.set(SESSION_COOKIE, "", { ...cookieOptions(), maxAge: 0 });
}

export async function hasSessionCookie(): Promise<boolean> {
  return Boolean((await cookies()).get(SESSION_COOKIE)?.value);
}
