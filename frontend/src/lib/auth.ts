"use server";

import { redirect } from "next/navigation";
import { dictionaries } from "./i18n";
import { getLanguage } from "./language";
import { isMockAuthEnabled, setMockSession } from "./session";

export type SignUpField =
  | "fullName"
  | "email"
  | "phone"
  | "password"
  | "confirmPassword"
  | "draftNotice";

export type SignUpState =
  | { status: "invalid"; errors: Partial<Record<SignUpField, string>> }
  | { status: "NOT_CONFIGURED"; message: string }
  | null;

export async function signUpLawyer(
  _state: SignUpState,
  formData: FormData,
): Promise<SignUpState> {
  const copy = dictionaries[await getLanguage()].lawyer.signup;
  const errors: Partial<Record<SignUpField, string>> = {};
  const text = (key: string) => String(formData.get(key) ?? "").trim();

  if (!text("fullName")) errors.fullName = copy.errors.required;

  const email = text("email");
  if (!email) errors.email = copy.errors.required;
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    errors.email = copy.errors.email;

  if (!text("phone")) errors.phone = copy.errors.required;

  const password = String(formData.get("password") ?? "");
  if (!password) errors.password = copy.errors.required;
  else if (password.length < 8) errors.password = copy.errors.passwordLength;

  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (!confirmPassword) errors.confirmPassword = copy.errors.required;
  else if (confirmPassword !== password)
    errors.confirmPassword = copy.errors.passwordMatch;

  if (formData.get("draftNotice") !== "on")
    errors.draftNotice = copy.errors.draftNotice;

  if (Object.keys(errors).length > 0) return { status: "invalid", errors };

  if (!isMockAuthEnabled() || !(await setMockSession("lawyer"))) {
    return { status: "NOT_CONFIGURED", message: copy.notConfigured };
  }

  redirect("/lawyer/dashboard");
}
