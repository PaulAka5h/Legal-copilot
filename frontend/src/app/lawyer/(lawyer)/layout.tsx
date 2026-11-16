import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { LawyerShell } from "@/components/lawyer/LawyerShell";
import { getLawyerProfile, listMatters } from "@/lib/api/lawyer";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

export default async function LawyerLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) redirect("/lawyer/login");
  if (session.role !== "lawyer") redirect("/client/dashboard");

  const language = await getLanguage();

  return (
    <LawyerShell
      language={language}
      profile={getLawyerProfile()}
      matterCount={listMatters().length}
    >
      {children}
    </LawyerShell>
  );
}
