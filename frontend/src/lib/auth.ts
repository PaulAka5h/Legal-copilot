"use server";

import { redirect } from "next/navigation";
import {
  BackendUnavailable,
  backendRequest,
} from "./api/backendClient";
import { dictionaries } from "./i18n";
import { getLanguage } from "./language";
import {
  isMockAuthEnabled,
  setMockSession,
  signInWithBackend,
} from "./session";

type Problem = {
  status?: number;
  errors?: Array<{ loc?: Array<string | number> }>;
};

async function readProblem(response: Response): Promise<Problem> {
  try {
    const problem = (await response.json()) as Problem;
    return { ...problem, status: problem.status ?? response.status };
  } catch {
    return { status: response.status };
  }
}

export type SignUpField =
  | "fullName"
  | "email"
  | "password"
  | "confirmPassword"
  | "draftNotice";

export type SignUpState =
  | { status: "invalid"; errors: Partial<Record<SignUpField, string>> }
  | { status: "error"; message: string }
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

  const password = String(formData.get("password") ?? "");
  if (!password) errors.password = copy.errors.required;
  else if (password.length < 12) errors.password = copy.errors.passwordLength;

  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (!confirmPassword) errors.confirmPassword = copy.errors.required;
  else if (confirmPassword !== password)
    errors.confirmPassword = copy.errors.passwordMatch;

  if (formData.get("draftNotice") !== "on")
    errors.draftNotice = copy.errors.draftNotice;

  if (Object.keys(errors).length > 0) return { status: "invalid", errors };

  if (isMockAuthEnabled()) {
    if (!(await setMockSession("lawyer"))) {
      return { status: "error", message: copy.notConfigured };
    }
    redirect("/lawyer/dashboard");
  }

  let response: Response;
  try {
    response = await backendRequest("/api/v1/auth/register", {
      method: "POST",
      json: {
        full_name: text("fullName"),
        email,
        password,
        preferred_language: await getLanguage(),
      },
    });
  } catch (error) {
    if (error instanceof BackendUnavailable) {
      return { status: "error", message: copy.errors.general };
    }
    throw error;
  }
  if (!response.ok) {
    const problem = await readProblem(response);
    const field = problem.errors?.[0]?.loc?.at(-1);
    if (field === "email" || problem.status === 409) errors.email = copy.errors.emailTaken;
    else if (field === "password") errors.password = copy.errors.passwordLength;
    else return { status: "error", message: copy.errors.general };
    return { status: "invalid", errors };
  }

  const login = await signInWithBackend(email, password, "lawyer");
  if (!login || "status" in login) {
    return { status: "error", message: copy.errors.general };
  }
  redirect("/lawyer/dashboard");
}
