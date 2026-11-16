import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getSession } from "@/lib/session";

export default async function ClientLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) redirect("/client/login");
  if (session.role !== "client") redirect("/lawyer/dashboard");

  return children;
}
