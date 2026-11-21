"use client";

import Link from "next/link";
import { useActionState, useState } from "react";
import { createClientAction } from "@/app/lawyer/actions";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import type { CreateClientError, CreateClientState } from "@/lib/api/lawyer";
import { dictionaries, format, type Language } from "@/lib/i18n";

export type CaseOption = { id: string; title: string };

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
const GENERATED_LENGTH = 16;

/** 16 letters and digits from the browser CSPRNG, without modulo bias. */
function generatePassword(): string {
  const limit = 256 - (256 % ALPHABET.length);
  let password = "";
  while (password.length < GENERATED_LENGTH) {
    for (const byte of crypto.getRandomValues(new Uint8Array(32))) {
      if (byte < limit && password.length < GENERATED_LENGTH) {
        password += ALPHABET[byte % ALPHABET.length];
      }
    }
  }
  return password;
}

function CredentialRow({
  label,
  value,
  copyLabel,
  copiedLabel,
}: {
  label: string;
  value: string;
  copyLabel: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div>
      <small>{label}</small>
      <b className="credential-value">{value}</b>
      <button type="button" onClick={copy} aria-label={`${copyLabel} ${label}`}>
        <Icon name="copy" size={18} />
        {copied ? copiedLabel : copyLabel}
      </button>
    </div>
  );
}

export function NewClientForm({
  language,
  cases,
}: {
  language: Language;
  cases: CaseOption[];
}) {
  const copy = dictionaries[language].newClient;
  const [state, formAction, pending] = useActionState<CreateClientState, FormData>(
    createClientAction,
    null,
  );
  const [dismissed, setDismissed] = useState(false);
  const [password, setPassword] = useState("");

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
            <CredentialRow
              label={copy.signInEmail}
              value={state.email}
              copyLabel={copy.copy}
              copiedLabel={copy.copied}
            />
            <CredentialRow
              label={copy.temporaryPassword}
              value={state.password}
              copyLabel={copy.copy}
              copiedLabel={copy.copied}
            />
          </div>

          <div className="security-callout" role="note">
            <Icon name="lock" size={18} />
            {copy.securityCallout}
          </div>

          {state.linkedCaseTitle ? (
            <p>{format(copy.linkedCase, { title: state.linkedCaseTitle })}</p>
          ) : null}

          <button
            className="primary-button"
            type="button"
            onClick={() => {
              setDismissed(true);
              setPassword("");
            }}
          >
            {copy.addAnother}
            <Icon name="plus" size={18} />
          </button>
        </div>
      </div>
    );
  }

  const errors: Record<CreateClientError, string> = {
    invalid: copy.error,
    general: copy.error,
    password: copy.passwordError,
    email_taken: copy.emailTaken,
    case: copy.caseError,
  };

  return (
    <form
      className="panel client-form"
      action={formAction}
      onSubmit={() => setDismissed(false)}
    >
      {state?.status === "error" ? (
        <p className="form-error" role="alert">
          {errors[state.reason]}
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
            autoComplete="off"
          />
        </Field>
        <div>
          <Field
            label={copy.password}
            icon="lock"
            action={
              <button
                type="button"
                className="field-action text-action"
                onClick={() => setPassword(generatePassword())}
              >
                {copy.generate}
              </button>
            }
          >
            <input
              name="password"
              type="text"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={12}
              maxLength={256}
              placeholder={copy.passwordPlaceholder}
              autoComplete="off"
              spellCheck={false}
              aria-describedby="client-password-hint"
            />
          </Field>
          <small className="field-hint" id="client-password-hint">
            {copy.passwordHint}
          </small>
        </div>
        <Field label={copy.caseLabel}>
          <select name="caseId" defaultValue="">
            <option value="">{copy.noCase}</option>
            {cases.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="form-actions">
        <Link className="ghost-button" href="/lawyer/clients">
          {copy.cancel}
        </Link>
        <button className="primary-button fit" type="submit" disabled={pending}>
          {copy.save}
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </form>
  );
}
