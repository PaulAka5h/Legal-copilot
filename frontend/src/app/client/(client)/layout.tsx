import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { ClientShell } from "@/components/client/ClientShell";
import { getClientProfile } from "@/lib/api/client";
import { getLanguage } from "@/lib/language";
import { getSession, hasSessionCookie, isMockAuthEnabled } from "@/lib/session";

export default async function ClientLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) {
    redirect((await hasSessionCookie()) ? "/auth/clear?next=/client/login" : "/client/login");
  }
  if (session.role !== "client") redirect("/lawyer/dashboard");

  const language = await getLanguage();

  return (
    <ClientShell
      language={language}
      profile={
        isMockAuthEnabled()
          ? getClientProfile()
          : { name: { en: session.full_name, bn: session.full_name } }
      }
    >
      {children}
    </ClientShell>
  );
}
