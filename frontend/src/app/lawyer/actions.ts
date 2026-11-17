"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  addDocument,
  addHearing,
  addHearingNote,
  approveHearingSummary,
  createClient,
  createMatter,
  downloadHearingSummary,
  getHearingSummary,
  saveHearingSummaryVersion,
  setCaseStage,
  setDocumentStatus,
  type CaseDocument,
  type ClaimType,
  type CreateClientState,
  type DocumentStatus,
  type NewDocumentInput,
  type SummarySection,
  type Verification,
} from "@/lib/api/lawyer";
import { getSession } from "@/lib/session";

const claimTypes: ClaimType[] = [
  "document",
  "lawyer",
  "ai",
  "assumption",
];
const verifications: Verification[] = ["verified", "unverified"];

function summaryPath(caseId: string, hearingId: string) {
  return `/lawyer/matters/${encodeURIComponent(caseId)}/hearings/${encodeURIComponent(hearingId)}/summary`;
}

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

export async function saveHearingSummaryAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  const hearingId = String(formData.get("hearingId") ?? "");
  const language = formData.get("language") === "bn" ? "bn" : "en";
  const path = summaryPath(caseId, hearingId);
  const current = getHearingSummary(caseId, hearingId);

  if (!caseId || !hearingId || !current) {
    redirect(`/lawyer/matters/${encodeURIComponent(caseId)}`);
  }

  let invalid = false;
  const sections: SummarySection[] = current.sections.map((section) => ({
    ...section,
    claims: section.claims.map((claim) => {
      const prefix = `claim:${section.id}:${claim.id}`;
      const text = String(formData.get(`${prefix}:text`) ?? "").trim();
      const source = String(formData.get(`${prefix}:source`) ?? "").trim();
      const type = String(
        formData.get(`${prefix}:type`) ?? claim.type,
      ) as ClaimType;
      const verification = String(
        formData.get(`${prefix}:verification`) ?? claim.verification,
      ) as Verification;

      if (
        !text ||
        !source ||
        !claimTypes.includes(type) ||
        !verifications.includes(verification)
      ) {
        invalid = true;
      }

      return {
        ...claim,
        type,
        verification,
        text: { ...claim.text, [language]: text },
        source: { ...claim.source, [language]: source },
      };
    }),
  }));

  if (invalid) redirect(`${path}?editError=1#editor`);

  const saved = saveHearingSummaryVersion(caseId, hearingId, sections);
  if (!saved) redirect(`${path}?editError=1#editor`);

  revalidatePath(path);
  revalidatePath(`/lawyer/matters/${caseId}`);
  revalidatePath("/client/dashboard");
  redirect(`${path}?saved=1#versions`);
}

export async function approveHearingSummaryAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  const hearingId = String(formData.get("hearingId") ?? "");
  const path = summaryPath(caseId, hearingId);

  if (!caseId || !hearingId || !approveHearingSummary(caseId, hearingId)) {
    redirect(`${path}?approveError=1#share`);
  }

  revalidatePath(path);
  revalidatePath(`/lawyer/matters/${caseId}`);
  revalidatePath("/client/dashboard");
  redirect(`${path}?approved=1#share`);
}

export async function downloadHearingSummaryAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  const hearingId = String(formData.get("hearingId") ?? "");
  const path = summaryPath(caseId, hearingId);

  if (!caseId || !hearingId || !getHearingSummary(caseId, hearingId)) {
    redirect(`/lawyer/matters/${encodeURIComponent(caseId)}`);
  }

  const download = downloadHearingSummary();
  redirect(`${path}?download=${download.status}#download`);
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
