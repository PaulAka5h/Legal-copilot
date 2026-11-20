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
  // Clients sign in with the email their invitation was sent to.
  return signIn("client", "clientId", formData);
}

export async function signOut() {
  const session = await getSession();
  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}
