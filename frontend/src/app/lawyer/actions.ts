"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  addFact,
  addHearing,
  addHearingNote,
  approveHearingSummary,
  confirmFact,
  editFact,
  createClient,
  createMatter,
  downloadHearingSummary,
  editMatter,
  extractFacts,
  getDocumentStatus,
  getHearingSummary,
  getLawyerProfileDetail,
  linkClientToCase,
  rejectFact,
  resetClientPassword,
  runAnalysis,
  runStrategy,
  saveHearingSummaryVersion,
  setMatterArchived,
  submitHearingUpdate,
  updateLawyerProfile,
  uploadDocument,
  type ActionResult,
  type CaseDocument,
  type ClaimType,
  type CreateClientState,
  type DocumentStatus,
  type FactCategory,
  type MatterStatus,
  type ResetPasswordState,
  type SummarySection,
  type Verification,
} from "@/lib/api/lawyer";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";
import { editLocalized } from "@/lib/summaryNotes";

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

async function requireLawyer() {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");
}

export async function createMatterAction(formData: FormData) {
  await requireLawyer();
  const matter = await createMatter({
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

const MATTER_STATUSES: MatterStatus[] = ["active", "on_hold", "closed"];

/** Pages that show case data; revalidated after any case change. */
function revalidateMatter(caseId: string) {
  revalidatePath(`/lawyer/matters/${caseId}`);
  revalidatePath("/lawyer/matters");
  revalidatePath("/lawyer/dashboard");
  revalidatePath("/client/dashboard");
}

/** Edit title, case type, court and status (audit-logged by the backend). */
export async function editMatterAction(formData: FormData) {
  await requireLawyer();
  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");
  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;
  const status = String(formData.get("status") ?? "") as MatterStatus;
  const result = MATTER_STATUSES.includes(status)
    ? await editMatter(caseId, {
        title: String(formData.get("title") ?? ""),
        caseType: String(formData.get("caseType") ?? ""),
        court: String(formData.get("court") ?? ""),
        status,
      })
    : "invalid";
  revalidateMatter(caseId);
  redirect(result === "ok" ? `${path}?edited=1` : `${path}?edit=1&editError=${result}#edit-case`);
}

/** Soft delete or restore (lead lawyer only; the backend enforces it and audits). */
export async function archiveMatterAction(formData: FormData) {
  await requireLawyer();
  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");
  const archive = formData.get("archive") === "1";
  const done = await setMatterArchived(caseId, archive);
  revalidateMatter(caseId);
  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;
  if (!done) redirect(`${path}?archiveError=1`);
  redirect(archive ? "/lawyer/matters?archivedCase=1" : `${path}?restored=1`);
}

export async function addHearingAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");

  const hearing = await addHearing(caseId, {
    date: String(formData.get("date") ?? ""),
    note: String(formData.get("note") ?? ""),
  });

  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;

  if (!hearing) redirect(`${path}?hearingError=1`);

  revalidateMatter(caseId);
  redirect(path);
}

export async function addHearingNoteAction(formData: FormData) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") redirect("/lawyer/login");

  const caseId = String(formData.get("caseId") ?? "");
  if (!caseId) redirect("/lawyer/matters");

  const hearing = await addHearingNote(
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
  const baseVersion = Number(formData.get("baseVersion"));
  const path = summaryPath(caseId, hearingId);
  const current = await getHearingSummary(caseId, hearingId);

  if (!caseId || !hearingId || !current) {
    redirect(`/lawyer/matters/${encodeURIComponent(caseId)}`);
  }
  // The editor was opened on an older version: never apply it over a newer one.
  if (!Number.isInteger(baseVersion) || baseVersion !== current.version) {
    redirect(`${path}?edit=1&editError=stale#editor`);
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
        text: editLocalized(claim.text, language, text),
        source: editLocalized(claim.source, language, source),
      };
    }),
  }));

  if (invalid) redirect(`${path}?edit=1&editError=invalid#editor`);

  const saved = await saveHearingSummaryVersion(caseId, hearingId, baseVersion, sections);
  if (saved !== "ok") redirect(`${path}?edit=1&editError=${saved}#editor`);

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

  if (!caseId || !hearingId || !(await approveHearingSummary(caseId, hearingId))) {
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
  const summary = await getHearingSummary(caseId, hearingId);

  if (!caseId || !hearingId || !summary) {
    redirect(`/lawyer/matters/${encodeURIComponent(caseId)}`);
  }

  const download = downloadHearingSummary();
  redirect(`${path}?download=${download.status}#download`);
}

/** Upload one file (FormData: caseId, hearingId, file). */
export async function uploadDocumentAction(
  formData: FormData,
): Promise<CaseDocument | null> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return null;

  const caseId = String(formData.get("caseId") ?? "");
  const hearingId = String(formData.get("hearingId") ?? "");
  const file = formData.get("file");
  if (!caseId || !(file instanceof File)) return null;

  const saved = await uploadDocument(caseId, hearingId, file);
  if (saved) revalidatePath(`/lawyer/matters/${caseId}`);
  return saved;
}

/** Current processing status of a document (demo documents move to demoStatus). */
export async function refreshDocumentStatusAction(
  caseId: string,
  documentId: string,
  demoStatus: DocumentStatus,
): Promise<DocumentStatus | null> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return null;

  return getDocumentStatus(caseId, documentId, demoStatus);
}

// ---------- case intelligence (facts, analysis, strategy, hearing updates) ----------

const FACT_CATEGORIES: FactCategory[] = [
  "party",
  "date",
  "place",
  "act_or_omission",
  "document",
  "relief_sought",
  "other",
];
const MAX_DETAIL = 240;

/** Back to the matter, on the given tab, with the outcome in the query string. */
function finish(caseId: string, tab: string, result: ActionResult): never {
  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;
  revalidatePath(path);
  const query = new URLSearchParams({ tab, ai: result.status });
  if (result.status === "error") query.set("detail", result.message.slice(0, MAX_DETAIL));
  redirect(`${path}?${query.toString()}`);
}

function field(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}

export async function addFactAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  const category = field(formData, "category") as FactCategory;
  const result = FACT_CATEGORIES.includes(category)
    ? await addFact(caseId, { statement: field(formData, "statement"), category })
    : ({ status: "error", message: "category" } as const);
  finish(caseId, "facts", result);
}

/** Stable prefix of the backend's confirm error when the quote is not on the cited page. */
const QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND";

export async function confirmFactAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  const factId = field(formData, "factId");
  const result = await confirmFact(caseId, factId);
  if (result.status === "error" && result.message.startsWith(QUOTE_NOT_FOUND)) {
    // A clear message and the Edit fact form for this fact, not a generic failure.
    const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;
    revalidatePath(path);
    const query = new URLSearchParams({ tab: "facts", ai: "quote_not_found", detail: factId });
    redirect(`${path}?${query.toString()}#fact-${encodeURIComponent(factId)}`);
  }
  finish(caseId, "facts", result);
}

export async function editFactAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  finish(
    caseId,
    "facts",
    await editFact(caseId, field(formData, "factId"), {
      statement: field(formData, "statement"),
      documentId: field(formData, "documentId"),
      page: Number(field(formData, "page")),
      quote: field(formData, "quote"),
    }),
  );
}

export async function rejectFactAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  const language = await getLanguage();
  const note = field(formData, "note") || dictionaries[language].caseDetail.ai.rejectDefault;
  finish(caseId, "facts", await rejectFact(caseId, field(formData, "factId"), note));
}

export async function extractFactsAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  finish(caseId, "facts", await extractFacts(caseId));
}

export async function runAnalysisAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  finish(caseId, "analysis", await runAnalysis(caseId));
}

export async function runStrategyAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  finish(caseId, "analysis", await runStrategy(caseId));
}

/** Record a hearing outcome; the backend re-runs analysis and strategy. */
export async function submitHearingUpdateAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  const nextDate = field(formData, "nextHearingDate");
  const result = await submitHearingUpdate(caseId, field(formData, "hearingId"), {
    orderText: field(formData, "orderText"),
    notes: field(formData, "notes"),
    nextHearingDate: /^\d{4}-\d{2}-\d{2}$/.test(nextDate) ? nextDate : null,
    nextHearingConfirmed: formData.get("nextHearingConfirmed") === "on",
  });
  revalidateMatter(caseId);
  finish(caseId, "hearings", result);
}

export async function createClientAction(
  _state: CreateClientState,
  formData: FormData,
): Promise<CreateClientState> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return { status: "error", reason: "general" };

  const result = await createClient({
    name: String(formData.get("name") ?? ""),
    phone: String(formData.get("phone") ?? ""),
    email: String(formData.get("email") ?? ""),
    // Passwords are never trimmed.
    password: String(formData.get("password") ?? ""),
    caseId: String(formData.get("caseId") ?? ""),
  });

  if ("error" in result) return { status: "error", reason: result.error };

  revalidatePath("/lawyer/clients");
  revalidatePath("/lawyer/dashboard");

  return { status: "ok", ...result };
}

export async function resetClientPasswordAction(
  _state: ResetPasswordState,
  formData: FormData,
): Promise<ResetPasswordState> {
  const session = await getSession();
  if (!session || session.role !== "lawyer") return { status: "error" };
  const clientId = String(formData.get("clientId") ?? "");
  if (!clientId) return { status: "error" };
  return resetClientPassword(clientId);
}

/** Give an existing client access to this case (case membership, role client). */
export async function linkClientToCaseAction(formData: FormData) {
  await requireLawyer();
  const caseId = field(formData, "caseId");
  if (!caseId) redirect("/lawyer/matters");
  const result = await linkClientToCase(caseId, field(formData, "clientId"));
  const path = `/lawyer/matters/${encodeURIComponent(caseId)}`;
  revalidatePath(path);
  revalidatePath("/lawyer/clients");
  redirect(`${path}?clientLink=${result}#client-access`);
}

/** Edit the lawyer profile (email is not editable; audit-logged by the backend). */
export async function updateProfileAction(formData: FormData) {
  await requireLawyer();
  const language = formData.get("preferredLanguage") === "bn" ? "bn" : "en";
  const result = await updateLawyerProfile(
    {
      fullName: String(formData.get("fullName") ?? ""),
      phone: String(formData.get("phone") ?? ""),
      preferredLanguage: language,
      chamberName: String(formData.get("chamberName") ?? ""),
      organizationName: String(formData.get("organizationName") ?? ""),
    },
    // Decided by the server (owner role), never by the form.
    Boolean((await getLawyerProfileDetail())?.canEditOrganization),
  );
  revalidatePath("/lawyer", "layout");
  redirect(result === "ok" ? "/lawyer/settings?profile=saved" : `/lawyer/settings?edit=1&profile=${result}#profile`);
}
