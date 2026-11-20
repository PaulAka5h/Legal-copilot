"use client";

import { useActionState, type ReactNode } from "react";
import type { LoginState } from "@/lib/session";

export type LoginAction = (state: LoginState, formData: FormData) => Promise<LoginState>;
type LoginFailure = NonNullable<LoginState>["status"];

export function MockLoginForm({
  action,
  notices,
  children,
}: {
  action: LoginAction;
  notices: Record<LoginFailure, string>;
  children: ReactNode;
}) {
  const [state, formAction] = useActionState(action, null);

  return (
    <form action={formAction}>
      {state ? (
        <p className="form-error" role="alert">
          {notices[state.status]}
        </p>
      ) : null}
      {children}
    </form>
  );
}
