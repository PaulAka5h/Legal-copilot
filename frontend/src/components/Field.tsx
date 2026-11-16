import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function Field({
  label,
  icon,
  children,
  action,
}: {
  label: ReactNode;
  icon?: IconName;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <span className="input-wrap">
        {icon ? <Icon name={icon} size={18} /> : null}
        {children}
        {action}
      </span>
    </label>
  );
}
