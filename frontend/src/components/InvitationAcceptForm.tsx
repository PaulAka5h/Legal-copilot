"use client";

import { useActionState } from "react";
import { acceptClientInvitation } from "@/app/actions";
import { Field } from "./Field";
import { PasswordField } from "./PasswordField";

export function InvitationAcceptForm({
  tokenLabel,
  passwordLabel,
  confirmLabel,
  submit,
  invalid,
  error,
  showPassword,
  hidePassword,
}: {
  tokenLabel: string;
  passwordLabel: string;
  confirmLabel: string;
  submit: string;
  invalid: string;
  error: string;
  showPassword: string;
  hidePassword: string;
}) {
  const [state, action] = useActionState(acceptClientInvitation, null);
  return (
    <form action={action}>
      {state ? <p className="form-error" role="alert">{state.status === "invalid" ? invalid : error}</p> : null}
      <Field label={tokenLabel} icon="lock">
        <input name="token" autoComplete="off" required aria-label={tokenLabel} />
      </Field>
      <PasswordField label={passwordLabel} ariaLabel={passwordLabel} defaultValue="" showLabel={showPassword} hideLabel={hidePassword} name="password" autoComplete="new-password" />
      <PasswordField label={confirmLabel} ariaLabel={confirmLabel} defaultValue="" showLabel={showPassword} hideLabel={hidePassword} name="confirmPassword" autoComplete="new-password" />
      <button className="primary-button" type="submit">{submit}</button>
    </form>
  );
}
