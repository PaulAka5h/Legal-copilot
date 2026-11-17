"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { resetClientPassword } from "@/lib/api/lawyer";
import { dictionaries, type Language } from "@/lib/i18n";

export function ResetPasswordButton({ language }: { language: Language }) {
  const copy = dictionaries[language].clientDetail;
  const [status, setStatus] = useState<"idle" | "NOT_CONFIGURED">("idle");

  return (
    <div className="reset-password">
      <button
        type="button"
        className="outline-button small"
        onClick={() => setStatus(resetClientPassword().status)}
      >
        <Icon name="lock" size={15} />
        {copy.resetPassword}
      </button>
      {status === "NOT_CONFIGURED" ? (
        <p className="reset-status" role="status">
          {copy.resetNotConfigured}
        </p>
      ) : null}
    </div>
  );
}
