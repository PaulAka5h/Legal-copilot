import Link from "next/link";
import { AuthLayout } from "@/components/AuthLayout";
import { ForgotPasswordForm } from "@/components/ForgotPasswordForm";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export default async function ForgotPasswordPage() {
  const language = await getLanguage();
  const copy = dictionaries[language].lawyer.forgotPassword;
  return (
    <AuthLayout type="lawyer" language={language} switcher={<Link href="/lawyer/login">{copy.back}</Link>}>
      <span className="eyebrow">{copy.eyebrow}</span>
      <h2>{copy.title}</h2>
      <p className="form-intro">{copy.intro}</p>
      <ForgotPasswordForm {...copy} emailLabel={dictionaries[language].lawyer.email} />
    </AuthLayout>
  );
}
