"use client";

import { useActionState, type ReactNode } from "react";
import type { LoginState } from "@/lib/session";

export type LoginAction = (state: LoginState, formData: FormData) => Promise<LoginState>;

export function MockLoginForm({
  action,
  notice,
  invalidMessage,
  rateLimitedMessage,
  children,
}: {
  action: LoginAction;
  notice: string;
  invalidMessage: string;
  rateLimitedMessage: string;
  children: ReactNode;
}) {
  const [state, formAction] = useActionState(action, null);

  return (
    <form action={formAction}>
      {state?.status && state.status !== "NOT_CONFIGURED" ? (
        <p className="form-error" role="alert">
          {state.status === "rate_limited" ? rateLimitedMessage : invalidMessage}
        </p>
      ) : state?.status === "NOT_CONFIGURED" ? (
        <p className="form-error" role="alert">
          {notice}
        </p>
      ) : null}
      {children}
    </form>
  );
}
