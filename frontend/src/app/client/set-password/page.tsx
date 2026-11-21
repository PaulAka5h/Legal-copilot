import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { signOut } from "@/app/actions";
import { AuthLayout } from "@/components/AuthLayout";
import { SetPasswordForm } from "@/components/SetPasswordForm";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientSetPassword") };
}

export default async function ClientSetPasswordPage() {
  const session = await getSession();
  if (!session) redirect("/client/login");
  if (!session.passwordChangeRequired) {
    redirect(session.role === "client" ? "/client/dashboard" : "/lawyer/dashboard");
  }

  const language = await getLanguage();
  const copy = dictionaries[language].client.setPassword;
  const lawyer = dictionaries[language].lawyer;

  return (
    <AuthLayout type="client" language={language}>
      <span className="eyebrow">{copy.eyebrow}</span>
      <h2>{copy.title}</h2>
      <p className="form-intro">{copy.intro}</p>
      <SetPasswordForm
        currentLabel={copy.currentLabel}
        passwordLabel={copy.passwordLabel}
        confirmLabel={copy.confirmLabel}
        submit={copy.submit}
        errors={copy.errors}
        showPassword={lawyer.showPassword}
        hidePassword={lawyer.hidePassword}
      />
      <form action={signOut}>
        <button className="ghost-button" type="submit">
          {dictionaries[language].common.signOut}
        </button>
      </form>
    </AuthLayout>
  );
}
