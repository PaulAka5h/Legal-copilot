"use client";

import { useActionState } from "react";
import { signUpLawyer } from "@/lib/auth";
import type { Dictionary } from "@/lib/i18n";
import { Field } from "./Field";
import { Icon } from "./Icon";
import { PasswordField } from "./PasswordField";

export function SignUpForm({ copy }: { copy: Dictionary["lawyer"] }) {
  const [state, formAction] = useActionState(signUpLawyer, null);
  const errors = state?.status === "invalid" ? state.errors : {};
  const signup = copy.signup;

  return (
    <form action={formAction}>
      {state?.status === "NOT_CONFIGURED" ? (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      ) : null}

      <Field
        label={signup.fullName}
        icon="user"
        error={errors.fullName}
        errorId="signup-fullName-error"
      >
        <input
          name="fullName"
          aria-label={signup.fullName}
          aria-required="true"
          autoComplete="name"
          aria-invalid={errors.fullName ? true : undefined}
          aria-describedby={
            errors.fullName ? "signup-fullName-error" : undefined
          }
        />
      </Field>

      <Field
        label={signup.email}
        icon="mail"
        error={errors.email}
        errorId="signup-email-error"
      >
        <input
          type="email"
          name="email"
          aria-label={signup.email}
          aria-required="true"
          autoComplete="email"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "signup-email-error" : undefined}
        />
      </Field>

      <Field
        label={signup.phone}
        icon="user"
        error={errors.phone}
        errorId="signup-phone-error"
      >
        <input
          type="tel"
          name="phone"
          aria-label={signup.phone}
          aria-required="true"
          autoComplete="tel"
          aria-invalid={errors.phone ? true : undefined}
          aria-describedby={errors.phone ? "signup-phone-error" : undefined}
        />
      </Field>

      <Field label={signup.firm} icon="briefcase">
        <input
          name="firm"
          aria-label={signup.firm}
          autoComplete="organization"
        />
      </Field>

      <Field label={signup.barEnrollment} icon="document">
        <input
          name="barEnrollment"
          aria-label={signup.barEnrollment}
          autoComplete="off"
        />
      </Field>

      <PasswordField
        label={signup.password}
        ariaLabel={signup.password}
        defaultValue=""
        showLabel={copy.showPassword}
        hideLabel={copy.hidePassword}
        name="password"
        autoComplete="new-password"
        error={errors.password}
        errorId="signup-password-error"
      />

      <PasswordField
        label={signup.confirmPassword}
        ariaLabel={signup.confirmPassword}
        defaultValue=""
        showLabel={copy.showPassword}
        hideLabel={copy.hidePassword}
        name="confirmPassword"
        autoComplete="new-password"
        error={errors.confirmPassword}
        errorId="signup-confirmPassword-error"
      />

      <div className="signup-check-row">
        <label className="check-label signup-check">
          <input
            type="checkbox"
            name="draftNotice"
            aria-required="true"
            aria-invalid={errors.draftNotice ? true : undefined}
            aria-describedby={
              errors.draftNotice ? "signup-draftNotice-error" : undefined
            }
          />
          <span>
            <Icon name="check" size={13} />
          </span>
          {signup.draftNotice}
        </label>
        {errors.draftNotice ? (
          <p className="field-error" id="signup-draftNotice-error">
            {errors.draftNotice}
          </p>
        ) : null}
      </div>

      <button className="primary-button signup-submit" type="submit">
        {signup.submit}
        <Icon name="arrow" size={19} />
      </button>
    </form>
  );
}
