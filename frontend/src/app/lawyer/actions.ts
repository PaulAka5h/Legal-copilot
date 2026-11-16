"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  createClient,
  createMatter,
  setCaseStage,
  type CreateClientState,
} from "@/lib/api/lawyer";
import { getSession } from "@/lib/session";

export async function createMatterAction(formData: FormData) {
  const matter = createMatter({
    title: String(formData.get("title") ?? ""),
    court: String(formData.get("court") ?? ""),
    caseType: String(formData.get("caseType") ?? ""),
    clientId: String(formData.get("clientId") ?? ""),
  });

  if (!matter) redirect("/lawyer/matters/new?error=1");

  revalidatePath("/lawyer/matters");
  revalidatePath("/lawyer/dashboard");
  redirect("/lawyer/matters");
}

export async function updateMatterStageAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  const stageId = String(formData.get("stageId") ?? "");

  if (!setCaseStage(caseId, stageId)) redirect("/lawyer/matters");

  revalidatePath(`/lawyer/matters/${caseId}`);
  revalidatePath("/lawyer/matters");
  revalidatePath("/lawyer/dashboard");
  redirect(`/lawyer/matters/${caseId}`);
}

export async function createClientAction(
  _state: CreateClientState,
  formData: FormData,
): Promise<CreateClientState> {
  const client = createClient({
    name: String(formData.get("name") ?? ""),
    phone: String(formData.get("phone") ?? ""),
    email: String(formData.get("email") ?? ""),
  });

  if (!client) return { status: "error" };

  revalidatePath("/lawyer/clients");
  revalidatePath("/lawyer/dashboard");

  return { status: "ok", ...client };
}
