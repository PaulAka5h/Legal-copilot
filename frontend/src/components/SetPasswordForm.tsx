"use client";

import { useActionState } from "react";
import { setNewPassword, type SetPasswordState } from "@/app/actions";
import { PasswordField } from "./PasswordField";

type Failure = NonNullable<SetPasswordState>["status"];

export function SetPasswordForm({
  currentLabel,
  passwordLabel,
  confirmLabel,
  submit,
  errors,
  showPassword,
  hidePassword,
}: {
  currentLabel: string;
  passwordLabel: string;
  confirmLabel: string;
  submit: string;
  errors: Record<Failure, string>;
  showPassword: string;
  hidePassword: string;
}) {
  const [state, action, pending] = useActionState(setNewPassword, null);
  const field = { defaultValue: "", showLabel: showPassword, hideLabel: hidePassword };
  return (
    <form action={action}>
      {state ? (
        <p className="form-error" role="alert">
          {errors[state.status]}
        </p>
      ) : null}
      <PasswordField {...field} label={currentLabel} ariaLabel={currentLabel} name="currentPassword" autoComplete="current-password" />
      <PasswordField {...field} label={passwordLabel} ariaLabel={passwordLabel} name="password" autoComplete="new-password" />
      <PasswordField {...field} label={confirmLabel} ariaLabel={confirmLabel} name="confirmPassword" autoComplete="new-password" />
      <button className="primary-button" type="submit" disabled={pending}>
        {submit}
      </button>
    </form>
  );
}
