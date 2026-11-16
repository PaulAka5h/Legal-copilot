import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getSession } from "@/lib/session";

export default async function LawyerLayout({ children }: { children: ReactNode }) {
  const session = await getSession();

  if (!session) redirect("/lawyer/login");
  if (session.role !== "lawyer") redirect("/client/dashboard");

  return children;
}
