"use client";

import { useActionState, type ReactNode } from "react";
import type { LoginState } from "@/lib/session";

export type LoginAction = (state: LoginState, formData: FormData) => Promise<LoginState>;

export function MockLoginForm({
  action,
  notice,
  children,
}: {
  action: LoginAction;
  notice: string;
  children: ReactNode;
}) {
  const [state, formAction] = useActionState(action, null);

  return (
    <form action={formAction}>
      {state?.status === "NOT_CONFIGURED" ? (
        <p className="form-error" role="alert">
          {notice}
        </p>
      ) : null}
      {children}
    </form>
  );
}
