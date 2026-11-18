"use client";

import { useState } from "react";
import { Field } from "./Field";
import { Icon } from "./Icon";

export function PasswordField({
  label,
  ariaLabel,
  defaultValue,
  showLabel,
  hideLabel,
  name = "password",
  autoComplete = "current-password",
  error,
  errorId,
}: {
  label: string;
  ariaLabel: string;
  defaultValue: string;
  showLabel: string;
  hideLabel: string;
  name?: string;
  autoComplete?: string;
  error?: string;
  errorId?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <Field
      label={label}
      icon="lock"
      error={error}
      errorId={errorId}
      action={
        <button
          type="button"
          className="field-action"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? hideLabel : showLabel}
        >
          <Icon name="eye" size={18} />
        </button>
      }
    >
      <input
        type={visible ? "text" : "password"}
        name={name}
        defaultValue={defaultValue}
        aria-label={ariaLabel}
        autoComplete={autoComplete}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
      />
    </Field>
  );
}
