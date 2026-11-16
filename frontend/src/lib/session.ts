import "server-only";

import { cookies } from "next/headers";

export type Role = "lawyer" | "client";
export type Session = { role: Role };
export type LoginState = { status: "NOT_CONFIGURED" } | null;

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
  if (!isMockAuthEnabled()) return null;

  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value?.startsWith(MOCK_PREFIX)) return null;

  const role = value.slice(MOCK_PREFIX.length);
  return role === "lawyer" || role === "client" ? { role } : null;
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
