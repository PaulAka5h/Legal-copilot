import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function Field({
  label,
  icon,
  children,
  action,
  error,
  errorId,
}: {
  label: ReactNode;
  icon?: IconName;
  children: ReactNode;
  action?: ReactNode;
  error?: string;
  errorId?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <span className="input-wrap">
        {icon ? <Icon name={icon} size={18} /> : null}
        {children}
        {action}
      </span>
      {error ? (
        <span className="field-error" id={errorId}>
          {error}
        </span>
      ) : null}
    </label>
  );
}
