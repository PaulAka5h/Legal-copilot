"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  clearSession,
  getSession,
  setMockSession,
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

async function mockSignIn(role: Role): Promise<LoginState> {
  if (!(await setMockSession(role))) {
    return { status: "NOT_CONFIGURED" };
  }

  redirect(role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
}

export async function lawyerLogin(): Promise<LoginState> {
  return mockSignIn("lawyer");
}

export async function clientLogin(): Promise<LoginState> {
  return mockSignIn("client");
}

export async function signOut() {
  const session = await getSession();
  await clearSession();
  redirect(session?.role === "client" ? "/client/login" : "/lawyer/login");
}
