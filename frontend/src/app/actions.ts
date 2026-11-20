"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { backendFetch, readProblem, relaySessionCookie } from "@/lib/api/backendClient";
import {
  clearSession,
  getSession,
  isMockAuthEnabled,
  setMockSession,
  type LoginState,
  type Role,
} from "@/lib/session";
import {
  createBackendClient,
  createBackendMatter,
} from "@/lib/api/lawyer";

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

async function signIn(role: Role, formData: FormData): Promise<LoginState> {
  if (isMockAuthEnabled()) {
    if (!(await setMockSession(role))) return { status: "NOT_CONFIGURED" };
    redirect(role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
  }

  const response = await backendFetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      email: String(formData.get("email") ?? "").trim(),
      password: String(formData.get("password") ?? ""),
      mfa_code: String(formData.get("mfaCode") ?? "").trim() || undefined,
    }),
  });
  if (!response.ok) {
    const problem = await readProblem(response);
    return problem.status === 429
      ? { status: "rate_limited", message: "rate_limited" }
      : { status: "invalid", message: "invalid", mfa: false };
  }
  const user = (await response.json()) as { role: Role };
  await relaySessionCookie(response);
  redirect(user.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
}

export async function lawyerLogin(
  _state: LoginState,
  formData: FormData,
): Promise<LoginState> {
  return signIn("lawyer", formData);
}

export async function clientLogin(
  _state: LoginState,
  formData: FormData,
): Promise<LoginState> {
  return signIn("client", formData);
}

export async function signOut() {
  const session = await getSession();
  if (!isMockAuthEnabled()) {
    const response = await backendFetch("/api/v1/auth/logout", { method: "POST" });
    await relaySessionCookie(response);
  }
  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}

export async function signOutAll() {
  const session = await getSession();
  if (!isMockAuthEnabled()) {
    const response = await backendFetch("/api/v1/auth/logout-all", { method: "POST" });
    await relaySessionCookie(response);
  }
  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}

export type ForgotPasswordState = { message: string } | null;

export async function requestPasswordReset(
  _state: ForgotPasswordState,
  formData: FormData,
): Promise<ForgotPasswordState> {
  const response = await backendFetch("/api/v1/auth/password/forgot", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: String(formData.get("email") ?? "").trim() }),
  });
  if (!response.ok) return { message: "error" };
  return { message: "sent" };
}

export type InvitationState = { status: "invalid" | "error"; message: string } | null;

export async function acceptClientInvitation(
  _state: InvitationState,
  formData: FormData,
): Promise<InvitationState> {
  const token = String(formData.get("token") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (!token || password.length < 12 || password !== confirmPassword) {
    return { status: "invalid", message: "invalid" };
  }
  const response = await backendFetch("/api/v1/auth/invitations/accept", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (!response.ok) return { status: "error", message: "error" };
  await relaySessionCookie(response);
  redirect("/client/dashboard");
}

export type CreateClientState =
  | null
  | ({ status: "ok" } & { name: string; clientId: string; password: string })
  | { status: "error"; message: string };

export async function createClient(
  _state: CreateClientState,
  formData: FormData,
): Promise<CreateClientState> {
  const name = String(formData.get("name") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();

  if (!name || !phone || !email || !/\S+@\S+\.\S+/.test(email)) {
    return { status: "error", message: "Invalid input" };
  }

  if (isMockAuthEnabled()) {
    const { createClient: createClientMock } = await import("@/lib/api/lawyer");
    const result = await createClientMock({ name, phone, email });
    if (!result) return { status: "error", message: "Failed to create client" };
    revalidatePath("/lawyer/clients");
    return { status: "ok", ...result };
  }

  const result = await createBackendClient({ name, phone, email });
  // createBackendClient never returns null, but TypeScript doesn't know that
  if (result && result.status === "error") {
    return { status: "error", message: result.message };
  }
  if (!result) {
    return { status: "error", message: "Failed to create client" };
  }
  revalidatePath("/lawyer/clients");
  return result;
}

export type CreateMatterState =
  | null
  | ({ status: "ok" } & { matterId: string })
  | { status: "error"; message: string };

export async function createMatter(
  _state: CreateMatterState,
  formData: FormData,
): Promise<CreateMatterState> {
  const title = String(formData.get("title") ?? "").trim();
  const court = String(formData.get("court") ?? "").trim();
  const caseType = String(formData.get("caseType") ?? "").trim();
  const clientId = String(formData.get("clientId") ?? "").trim();

  if (!title || !court || !caseType || !clientId) {
    return { status: "error", message: "Invalid input" };
  }

  if (isMockAuthEnabled()) {
    const result = await import("@/lib/api/lawyer").then((m) =>
      m.createMatter({ title, court, caseType, clientId }),
    );
    if (!result) return { status: "error", message: "Failed to create case" };
    revalidatePath("/lawyer/matters");
    return { status: "ok", matterId: result.id };
  }

  const result = await createBackendMatter({ title, court, caseType, clientId });
  if ("status" in result && result.status === "error") {
    return { status: "error", message: result.detail };
  }
  revalidatePath("/lawyer/matters");
  return { status: "ok", matterId: result.id };
}
