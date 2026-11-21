"use client";

import { useActionState, useState } from "react";
import { resetClientPasswordAction } from "@/app/lawyer/actions";
import { Icon } from "@/components/Icon";
import type { ResetPasswordState } from "@/lib/api/lawyer";
import { dictionaries, type Language } from "@/lib/i18n";

/** Resets the client's password and shows the new temporary one exactly once. */
export function ResetPasswordButton({
  language,
  clientId,
}: {
  language: Language;
  clientId: string;
}) {
  const copy = dictionaries[language].clientDetail;
  const [state, formAction, pending] = useActionState<ResetPasswordState, FormData>(
    resetClientPasswordAction,
    null,
  );
  const [copied, setCopied] = useState(false);

  async function copyPassword(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="reset-password">
      <form
        action={formAction}
        onSubmit={(event) => {
          if (!window.confirm(copy.resetConfirm)) event.preventDefault();
          else setCopied(false);
        }}
      >
        <input type="hidden" name="clientId" value={clientId} />
        <button type="submit" className="outline-button small" disabled={pending}>
          <Icon name="lock" size={15} />
          {copy.resetPassword}
        </button>
      </form>
      {state?.status === "ok" ? (
        <div className="credentials" role="status">
          <div>
            <small>{copy.resetDone}</small>
            <b className="credential-value">{state.password}</b>
            <button
              type="button"
              onClick={() => copyPassword(state.password)}
              aria-label={`${copy.copy} ${copy.resetDone}`}
            >
              <Icon name="copy" size={18} />
              {copied ? copy.copied : copy.copy}
            </button>
          </div>
          <p className="reset-status">{copy.resetWarning}</p>
        </div>
      ) : null}
      {state?.status === "error" ? (
        <p className="reset-status" role="alert">
          {copy.resetError}
        </p>
      ) : null}
      {state?.status === "NOT_CONFIGURED" ? (
        <p className="reset-status" role="status">
          {copy.resetNotConfigured}
        </p>
      ) : null}
    </div>
  );
}
