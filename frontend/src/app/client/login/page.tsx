import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { clientLogin } from "@/app/actions";
import { AuthLayout } from "@/components/AuthLayout";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import { MockLoginForm } from "@/components/MockLoginForm";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { SAMPLE_CLIENT_LOGIN } from "@/lib/sample";
import { getSession, isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientLogin") };
}

export default async function ClientLoginPage() {
  const session = await getSession();
  if (session) {
    redirect(session.role === "client" ? "/client/dashboard" : "/lawyer/dashboard");
  }

  const language = await getLanguage();
  const copy = dictionaries[language].client;
  const common = dictionaries[language].common;

  return (
    <AuthLayout
      type="client"
      language={language}
      switcher={
        <>
          {copy.switchPrompt} <Link href="/lawyer/login">{copy.switchAction}</Link>
        </>
      }
    >
      <span className="eyebrow">{copy.portal}</span>
      <h2>{copy.title}</h2>
      <p className="form-intro">{copy.intro}</p>
      {isMockAuthEnabled() ? <p className="mock-note">{common.mockNotice}</p> : null}
      <MockLoginForm action={clientLogin} notice={common.mockDisabled}>
        <Field label={copy.clientId} icon="user">
          <input
            name="clientId"
            defaultValue={SAMPLE_CLIENT_LOGIN.clientId}
            aria-label={copy.clientId}
            autoComplete="username"
          />
        </Field>
        <Field label={copy.password} icon="lock">
          <input
            type="password"
            name="password"
            defaultValue={SAMPLE_CLIENT_LOGIN.password}
            aria-label={copy.password}
            autoComplete="current-password"
          />
        </Field>
        <button className="primary-button" type="submit">
          {copy.submit}
          <Icon name="arrow" size={19} />
        </button>
      </MockLoginForm>
      <div className="help-note">
        <Icon name="lock" size={17} />
        <span>
          {copy.helpTitle}
          <small>{copy.helpBody}</small>
        </span>
      </div>
    </AuthLayout>
  );
}
