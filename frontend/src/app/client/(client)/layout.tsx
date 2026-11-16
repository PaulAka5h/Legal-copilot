import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { ClientShell } from "@/components/client/ClientShell";
import { getClientProfile } from "@/lib/api/client";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

export default async function ClientLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) redirect("/client/login");
  if (session.role !== "client") redirect("/lawyer/dashboard");

  const language = await getLanguage();

  return (
    <ClientShell language={language} profile={getClientProfile()}>
      {children}
    </ClientShell>
  );
}
