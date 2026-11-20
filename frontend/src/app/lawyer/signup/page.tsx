import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import "./signup.css";
import { AuthLayout } from "@/components/AuthLayout";
import { SignUpForm } from "@/components/SignUpForm";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { getSession, hasSessionCookie, isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerSignup") };
}

export default async function LawyerSignupPage() {
  const session = await getSession();
  if (session) {
    redirect(
      session.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard",
    );
  }
  if (await hasSessionCookie()) redirect("/auth/clear?next=/lawyer/signup");

  const language = await getLanguage();
  const copy = dictionaries[language].lawyer;
  const signup = copy.signup;

  return (
    <AuthLayout
      type="lawyer"
      language={language}
      switcher={
        <>
          {copy.alreadyPrompt}{" "}
          <Link href="/lawyer/login">{copy.loginAction}</Link>
        </>
      }
    >
      <span className="eyebrow">{copy.portal}</span>
      <h2>{signup.title}</h2>
      <p className="form-intro">{signup.intro}</p>
      {isMockAuthEnabled() ? (
        <p className="mock-note">{signup.mockNotice}</p>
      ) : null}
      <SignUpForm copy={copy} />
    </AuthLayout>
  );
}
