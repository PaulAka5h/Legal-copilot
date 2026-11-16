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
}: {
  label: string;
  ariaLabel: string;
  defaultValue: string;
  showLabel: string;
  hideLabel: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <Field
      label={label}
      icon="lock"
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
        name="password"
        defaultValue={defaultValue}
        aria-label={ariaLabel}
        autoComplete="current-password"
      />
    </Field>
  );
}
