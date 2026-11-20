"use client";

import Link from "next/link";
import { useActionState, useState } from "react";
import { createClientAction } from "@/app/lawyer/actions";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import type { CreateClientState } from "@/lib/api/lawyer";
import { dictionaries, format, type Language } from "@/lib/i18n";

export function NewClientForm({ language }: { language: Language }) {
  const copy = dictionaries[language].newClient;
  const [state, formAction] = useActionState<CreateClientState, FormData>(
    createClientAction,
    null,
  );
  const [dismissed, setDismissed] = useState(false);
  const [copied, setCopied] = useState<"id" | "password" | null>(null);

  async function copyValue(value: string, field: "id" | "password") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(field);
    } catch {
      return;
    }
  }

  if (state?.status === "ok" && !dismissed) {
    return (
      <div className="success-wrap">
        <div className="success-card">
          <span className="success-icon">
            <Icon name="check" size={30} />
          </span>
          <span className="eyebrow">{copy.createdEyebrow}</span>
          <h1>{format(copy.ready, { name: state.name })}</h1>
          <p>{copy.shareWithClient}</p>

          <div className="credentials">
            <div>
              <small>{copy.clientId}</small>
              <b>{state.clientId}</b>
              <button
                type="button"
                onClick={() => copyValue(state.clientId, "id")}
                aria-label={`${copy.copy} ${copy.clientId}`}
              >
                <Icon name="copy" size={18} />
                {copied === "id" ? copy.copied : copy.copy}
              </button>
            </div>
            <div>
              <small>{copy.temporaryPassword}</small>
              <b>{state.password}</b>
              <button
                type="button"
                onClick={() => copyValue(state.password, "password")}
                aria-label={`${copy.copy} ${copy.temporaryPassword}`}
              >
                <Icon name="copy" size={18} />
                {copied === "password" ? copy.copied : copy.copy}
              </button>
            </div>
          </div>

          <div className="security-callout">
            <Icon name="lock" size={18} />
            {copy.securityCallout}
          </div>

          <p className="mock-note">{copy.mockGenerated}</p>

          <button
            className="primary-button"
            type="button"
            onClick={() => {
              setDismissed(true);
              setCopied(null);
            }}
          >
            {copy.addAnother}
            <Icon name="plus" size={18} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <form
      className="panel client-form"
      action={formAction}
      onSubmit={() => setDismissed(false)}
    >
      {state?.status === "error" ? (
        <p className="form-error" role="alert">
          {"message" in state && state.message === "organization"
            ? copy.organizationError
            : copy.error}
        </p>
      ) : null}

      <div className="form-section-head">
        <span>01</span>
        <div>
          <h2>{copy.sectionTitle}</h2>
          <p>{copy.sectionBody}</p>
        </div>
      </div>

      <div className="form-grid">
        <div className="full">
          <Field label={copy.name}>
            <input
              name="name"
              required
              placeholder={copy.namePlaceholder}
              autoComplete="name"
            />
          </Field>
        </div>
        <Field label={copy.phone}>
          <input
            name="phone"
            type="tel"
            required
            placeholder={copy.phonePlaceholder}
            autoComplete="tel"
          />
        </Field>
        <Field label={copy.email}>
          <input
            name="email"
            type="email"
            required
            placeholder={copy.emailPlaceholder}
            autoComplete="email"
          />
        </Field>
      </div>

      <div className="form-actions">
        <Link className="ghost-button" href="/lawyer/clients">
          {copy.cancel}
        </Link>
        <button className="primary-button fit" type="submit">
          {copy.save}
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </form>
  );
}
