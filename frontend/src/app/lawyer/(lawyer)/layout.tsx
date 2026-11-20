import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { LawyerShell } from "@/components/lawyer/LawyerShell";
import { getLawyerProfile, listMatters } from "@/lib/api/lawyer";
import { getLanguage } from "@/lib/language";
import { getSession, hasSessionCookie, isMockAuthEnabled } from "@/lib/session";

export default async function LawyerLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) {
    redirect((await hasSessionCookie()) ? "/auth/clear?next=/lawyer/login" : "/lawyer/login");
  }
  if (session.role !== "lawyer") redirect("/client/dashboard");

  const language = await getLanguage();

  return (
    <LawyerShell
      language={language}
      profile={
        isMockAuthEnabled()
          ? getLawyerProfile()
          : {
              firstName: { en: session.full_name, bn: session.full_name },
              name: { en: session.full_name, bn: session.full_name },
              email: session.email,
              firm: { en: "", bn: "" },
              location: { en: "", bn: "" },
            }
      }
      matterCount={isMockAuthEnabled() ? listMatters().length : 0}
    >
      {children}
    </LawyerShell>
  );
}
