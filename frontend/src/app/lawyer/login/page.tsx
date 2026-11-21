import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { lawyerLogin } from "@/app/actions";
import { AuthLayout } from "@/components/AuthLayout";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import { MockLoginForm } from "@/components/MockLoginForm";
import { PasswordField } from "@/components/PasswordField";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { getSession, isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerLogin") };
}

export default async function LawyerLoginPage() {
  const session = await getSession();
  if (session) {
    redirect(session.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
  }

  const language = await getLanguage();
  const copy = dictionaries[language].lawyer;
  const common = dictionaries[language].common;

  return (
    <AuthLayout
      type="lawyer"
      language={language}
      switcher={
        <>
          <Link href="/client/login">{copy.switchAction}</Link>
          <span className="mt-3 block">
            {copy.newHere}{" "}
            <Link href="/lawyer/signup">{copy.createAccount}</Link>
          </span>
        </>
      }
    >
      <span className="eyebrow">{copy.portal}</span>
      <h2>{copy.welcome}</h2>
      <p className="form-intro">{copy.intro}</p>
      {isMockAuthEnabled() ? <p className="mock-note">{common.mockNotice}</p> : null}
      <MockLoginForm action={lawyerLogin} notices={{
          NOT_CONFIGURED: common.mockDisabled,
          INVALID: common.loginInvalid,
          UNAVAILABLE: common.loginUnavailable,
        }}>
        <Field label={copy.email} icon="mail">
          <input
            type="email"
            name="email"
            aria-label={copy.email}
            autoComplete="email"
          />
        </Field>
        <PasswordField
          label={copy.password}
          ariaLabel={copy.password}
          showLabel={copy.showPassword}
          hideLabel={copy.hidePassword}
        />
        <div className="form-row">
          <label className="check-label">
            <input type="checkbox" name="remember" defaultChecked />
            <span>
              <Icon name="check" size={13} />
            </span>
            {copy.remember}
          </label>
          <button type="button" className="text-link">
            {copy.forgot}
          </button>
        </div>
        <button className="primary-button" type="submit">
          {copy.signIn}
          <Icon name="arrow" size={19} />
        </button>
      </MockLoginForm>
    </AuthLayout>
  );
}
