"use server";

import { redirect } from "next/navigation";
import { downloadClientSummary, getApprovedSummary } from "@/lib/api/client";
import { getSession } from "@/lib/session";

export async function downloadClientSummaryAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "client") redirect("/client/login");

  const summaryId = String(formData.get("summaryId") ?? "");
  if (!summaryId || !(await getApprovedSummary(summaryId))) {
    redirect("/client/dashboard");
  }

  const download = downloadClientSummary();
  redirect(
    `/client/summaries/${encodeURIComponent(summaryId)}?download=${download.status}#download`,
  );
}
