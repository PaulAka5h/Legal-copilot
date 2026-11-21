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
import { getSession, readyDestination } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientLogin") };
}

export default async function ClientLoginPage() {
  const session = await getSession();
  const destination = await readyDestination(session);
  if (destination) redirect(destination);

  const language = await getLanguage();
  const copy = dictionaries[language].client;
  const common = dictionaries[language].common;

  return (
    <AuthLayout
      type="client"
      language={language}
      switcher={<Link href="/lawyer/login">{copy.switchAction}</Link>}
    >
      <span className="eyebrow">{copy.portal}</span>
      <h2>{copy.title}</h2>
      <p className="form-intro">{copy.intro}</p>
      <MockLoginForm action={clientLogin} notices={{
          NOT_CONFIGURED: common.mockDisabled,
          INVALID: common.loginInvalid,
          UNAVAILABLE: common.loginUnavailable,
        }}>
        <Field label={copy.email} icon="user">
          <input
            name="email"
            aria-label={copy.email}
            autoComplete="username"
          />
        </Field>
        <Field label={copy.password} icon="lock">
          <input
            type="password"
            name="password"
            aria-label={copy.password}
            autoComplete="current-password"
          />
        </Field>
        <button className="primary-button" type="submit">
          {copy.submit}
          <Icon name="arrow" size={19} />
        </button>
      </MockLoginForm>
    </AuthLayout>
  );
}
