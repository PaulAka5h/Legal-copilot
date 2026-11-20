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
import { SAMPLE_LAWYER_LOGIN } from "@/lib/sample";
import { getSession, hasSessionCookie, isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerLogin") };
}

export default async function LawyerLoginPage() {
  const session = await getSession();
  if (session) {
    redirect(session.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard");
  }
  if (await hasSessionCookie()) redirect("/auth/clear?next=/lawyer/login");

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
      <MockLoginForm
        action={lawyerLogin}
        notice={common.mockDisabled}
        invalidMessage={copy.invalidCredentials}
        rateLimitedMessage={copy.rateLimited}
      >
        <Field label={copy.email} icon="mail">
          <input
            type="email"
            name="email"
            defaultValue={isMockAuthEnabled() ? SAMPLE_LAWYER_LOGIN.email : ""}
            aria-label={copy.email}
            autoComplete="email"
          />
        </Field>
        <PasswordField
          label={copy.password}
          ariaLabel={copy.password}
          defaultValue={isMockAuthEnabled() ? SAMPLE_LAWYER_LOGIN.password : ""}
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
          <Link className="text-link" href="/lawyer/forgot-password">
            {copy.forgot}
          </Link>
        </div>
        <button className="primary-button" type="submit">
          {copy.signIn}
          <Icon name="arrow" size={19} />
        </button>
      </MockLoginForm>
    </AuthLayout>
  );
}
