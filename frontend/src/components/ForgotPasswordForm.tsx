"use client";

import { useActionState } from "react";
import { requestPasswordReset } from "@/app/actions";
import { Field } from "./Field";

export function ForgotPasswordForm({
  emailLabel,
  submit,
  sent,
  error,
}: {
  emailLabel: string;
  submit: string;
  sent: string;
  error: string;
}) {
  const [state, action] = useActionState(requestPasswordReset, null);
  return (
    <form action={action}>
      {state ? <p className="form-error" role="status">{state.message === "sent" ? sent : error}</p> : null}
      <Field label={emailLabel} icon="mail">
        <input type="email" name="email" autoComplete="email" required aria-label={emailLabel} />
      </Field>
      <button className="primary-button" type="submit">{submit}</button>
    </form>
  );
}
