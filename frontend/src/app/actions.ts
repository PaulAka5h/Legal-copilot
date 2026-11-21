"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  clearSession,
  getSession,
  isMockAuthEnabled,
  setMockSession,
  signInWithBackend,
  type LoginState,
  type Role,
} from "@/lib/session";
import {
  BackendUnavailable,
  MOCK_PREFIX,
  SESSION_COOKIE,
  backendRequest,
} from "@/lib/api/backendClient";

export async function setLanguage(formData: FormData) {
  const language = formData.get("language") === "bn" ? "bn" : "en";
  const store = await cookies();
  store.set("lang", language, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  revalidatePath("/", "layout");
}

async function signIn(
  role: Role,
  login: string,
  formData: FormData,
): Promise<LoginState> {
  if (isMockAuthEnabled()) {
    if (!(await setMockSession(role))) return { status: "NOT_CONFIGURED" };
    redirect(role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
  }

  const email = String(formData.get(login) ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return { status: "INVALID" };

  const result = await signInWithBackend(email, password);
  if (result && "role" in result) {
    if (result.mustChangePassword) redirect("/client/set-password");
    // The backend decides the role, whichever portal the form was on.
    redirect(result.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
  }
  return result;
}

export async function lawyerLogin(
  _state: LoginState,
  formData: FormData,
): Promise<LoginState> {
  return signIn("lawyer", "email", formData);
}

export async function clientLogin(
  _state: LoginState,
  formData: FormData,
): Promise<LoginState> {
  // Clients sign in with the email their lawyer registered for them.
  return signIn("client", "email", formData);
}

export async function signOut() {
  const session = await getSession();
  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}

export async function signOutAll() {
  const session = await getSession();
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;

  if (token && !token.startsWith(MOCK_PREFIX)) {
    try {
      await backendRequest("/api/v1/auth/logout-all", {
        method: "POST",
        token,
      });
    } catch {
      // Local sign-out must still succeed if the backend is unavailable.
    }
  }

  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}

export type PasswordResetState = { message: "sent" | "error" } | null;

export async function requestPasswordReset(
  _state: PasswordResetState,
  formData: FormData,
): Promise<PasswordResetState> {
  const email = String(formData.get("email") ?? "").trim();
  if (!email) return { message: "error" };

  try {
    const response = await backendRequest("/api/v1/auth/password/forgot", {
      method: "POST",
      json: { email },
    });
    return { message: response.ok ? "sent" : "error" };
  } catch (error) {
    if (error instanceof BackendUnavailable) return { message: "error" };
    throw error;
  }
}

export type InvitationState =
  | { status: "invalid" }
  | { status: "error" }
  | null;

export async function acceptClientInvitation(
  _state: InvitationState,
  formData: FormData,
): Promise<InvitationState> {
  const token = String(formData.get("token") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");

  if (
    token.length < 32 ||
    password.length < 12 ||
    password !== confirmPassword
  ) {
    return { status: "invalid" };
  }

  let response: Response;
  try {
    response = await backendRequest("/api/v1/auth/invitations/accept", {
      method: "POST",
      json: { token, password },
    });
  } catch (error) {
    if (error instanceof BackendUnavailable) return { status: "error" };
    throw error;
  }
  if (!response.ok) {
    return { status: response.status === 400 || response.status === 422 ? "invalid" : "error" };
  }

  for (const header of response.headers.getSetCookie()) {
    const [pair] = header.split(";");
    const index = pair.indexOf("=");
    if (pair.slice(0, index).trim() === SESSION_COOKIE) {
      const sessionToken = pair.slice(index + 1).trim();
      if (sessionToken) {
        const store = await cookies();
        store.set(SESSION_COOKIE, sessionToken, {
          httpOnly: true,
          sameSite: "lax",
          secure: process.env.NODE_ENV === "production",
          path: "/",
          maxAge: 60 * 60 * 8,
        });
        redirect("/client/dashboard");
      }
    }
  }

  return { status: "error" };
}

export type SetPasswordState =
  | { status: "mismatch" }
  | { status: "length" }
  | { status: "same" }
  | { status: "current" }
  | { status: "error" }
  | null;

/** Replace a temporary password; required before the backend serves anything else. */
export async function setNewPassword(
  _state: SetPasswordState,
  formData: FormData,
): Promise<SetPasswordState> {
  const current = String(formData.get("currentPassword") ?? "");
  const password = String(formData.get("password") ?? "");
  const confirm = String(formData.get("confirmPassword") ?? "");
  if (password.length < 12) return { status: "length" };
  if (password !== confirm) return { status: "mismatch" };
  if (password === current) return { status: "same" };

  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token || token.startsWith(MOCK_PREFIX)) redirect("/client/login");

  let response: Response;
  try {
    response = await backendRequest("/api/v1/auth/password/change", {
      method: "POST",
      json: { current_password: current, new_password: password },
      token,
    });
  } catch (error) {
    if (error instanceof BackendUnavailable) return { status: "error" };
    throw error;
  }
  if (response.status === 401) redirect("/client/login");
  if (response.status === 400) return { status: "current" };
  if (response.status === 422) return { status: "length" };
  if (!response.ok) return { status: "error" };
  const user = (await response.json()) as { role?: string };
  redirect(user.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
}
