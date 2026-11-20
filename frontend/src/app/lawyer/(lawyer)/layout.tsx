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
  const [profile, matters] = await Promise.all([getLawyerProfile(), listMatters()]);

  return (
    <LawyerShell
      language={language}
      profile={profile}
      matterCount={matters.length}
    >
      {children}
    </LawyerShell>
  );
}
