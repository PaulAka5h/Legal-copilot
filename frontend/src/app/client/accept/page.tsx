import { AuthLayout } from "@/components/AuthLayout";
import { InvitationAcceptForm } from "@/components/InvitationAcceptForm";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export default async function ClientAcceptInvitationPage() {
  const language = await getLanguage();
  const copy = dictionaries[language].client.acceptInvitation;
  return (
    <AuthLayout type="client" language={language}>
      <span className="eyebrow">{copy.eyebrow}</span>
      <h2>{copy.title}</h2>
      <p className="form-intro">{copy.intro}</p>
      <InvitationAcceptForm {...copy} showPassword={dictionaries[language].lawyer.showPassword} hidePassword={dictionaries[language].lawyer.hidePassword} />
    </AuthLayout>
  );
}
