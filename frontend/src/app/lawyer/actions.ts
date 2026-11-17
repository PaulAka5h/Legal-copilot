"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  addDocument,
  addHearing,
  addHearingNote,
  createClient,
  createMatter,
  setCaseStage,
  setDocumentStatus,
  type CaseDocument,
  type CreateClientState,
  type DocumentStatus,
  type NewDocumentInput,
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

export async function addHearingAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");

  const hearing = addHearing(caseId, {
    date: String(formData.get("date") ?? ""),
    note: String(formData.get("note") ?? ""),
  });

  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;

  if (!hearing) redirect(`${path}?hearingError=1`);

  revalidatePath(path);
  revalidatePath("/lawyer/matters");
  revalidatePath("/lawyer/dashboard");
  redirect(path);
}

export async function addHearingNoteAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");

  const hearing = addHearingNote(
    caseId,
    String(formData.get("hearingId") ?? ""),
    String(formData.get("note") ?? ""),
  );

  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;

  if (!hearing) redirect(`${path}?noteError=1`);

  revalidatePath(path);
  redirect(path);
}

export async function uploadDocumentAction(input: {
  caseId: string;
} & NewDocumentInput): Promise<CaseDocument | null> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return null;

  return addDocument(input.caseId, input);
}

export async function setDocumentStatusAction(
  caseId: string,
  documentId: string,
  status: DocumentStatus,
): Promise<boolean> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return false;

  return setDocumentStatus(caseId, documentId, status);
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
