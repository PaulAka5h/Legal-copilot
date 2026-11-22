import "server-only";

import {
  BackendError,
  backend,
  backendOrNull,
  backendRequest,
  caseUrl,
  sessionToken,
  withDemoFallback,
  type Api,
} from "@/lib/api/backendClient";
import * as demo from "@/lib/api/lawyerDemo";
import type {
  ActionResult,
  Activity,
  CaseAnalysis,
  CaseDocument,
  CaseFact,
  CaseIntelligence,
  Citation,
  ClientCredentials,
  ClientDetail,
  CreateClientError,
  ClientSummary,
  DocumentStatus,
  EditFactInput,
  EditMatterInput,
  EditMatterResult,
  Hearing,
  HearingSummary,
  HearingUpdateInput,
  LawyerProfile,
  LawyerProfileDetail,
  LawyerStats,
  Localized,
  Matter,
  MatterStatus,
  NewClientInput,
  NewFactInput,
  NewHearingInput,
  NewMatterInput,
  ProfileInput,
  Reassessment,
  ResetPasswordState,
  Strength,
  StrategyMove,
  StrategyTree,
  SummaryClaim,
  SummarySection,
  Verification,
} from "@/lib/api/lawyerTypes";
import { isValidProfileInput, nfc, normalizeBdPhone } from "@/lib/api/lawyerProfile";
import { dictionaries, format, numberFor, pick, type Language } from "@/lib/i18n";
import { getSession } from "@/lib/session";
import { currentKeyNotes } from "@/lib/summaryNotes";

export type * from "@/lib/api/lawyerTypes";

/*
 * Lawyer data. Every function calls the backend as the signed-in user and
 * adapts the response to the UI shapes in lawyerTypes.ts. When the backend is
 * unreachable (or under development mock sign-in) it falls back to the
 * in-memory demo data and the page shows a demo-data label.
 */

type HearingRow = Api["HearingOut"];
type TimelineRow = Api["TimelineEntry"];
type ReassessmentRow = Api["HearingReassessment"];

const STRENGTHS: readonly Strength[] = ["strong", "moderate", "weak", "insufficient"];

function same(text: string | null | undefined): Localized {
  const value = text ?? "";
  return { en: value, bn: value };
}

function dateParts(iso: string, options: Intl.DateTimeFormatOptions): Localized {
  const date = new Date(iso);
  return {
    en: new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", ...options }).format(date),
    bn: new Intl.DateTimeFormat("bn-BD", { timeZone: "Asia/Dhaka", ...options }).format(date),
  };
}

function verification(verified: boolean): Verification {
  return verified ? "verified" : "unverified";
}

function strengthOf(value: string | null | undefined): Strength | null {
  return STRENGTHS.find((item) => item === value) ?? null;
}

function sortHearings(rows: HearingRow[]): HearingRow[] {
  return [...rows].sort((a, b) =>
    (a.scheduled_at ?? a.created_at).localeCompare(b.scheduled_at ?? b.created_at),
  );
}

// ---------- matters ----------

function nextHearingOf(rows: HearingRow[]): Matter["nextHearing"] {
  const now = Date.now();
  const next = sortHearings(rows).find(
    (row) =>
      row.date_status === "confirmed" &&
      row.scheduled_at !== null &&
      new Date(row.scheduled_at).getTime() >= now,
  );
  if (!next?.scheduled_at) return undefined;
  return {
    day: Number(
      new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", day: "numeric" }).format(
        new Date(next.scheduled_at),
      ),
    ),
    month: dateParts(next.scheduled_at, { month: "short" }),
    time: dateParts(next.scheduled_at, { hour: "2-digit", minute: "2-digit" }),
  };
}

const STATUS: Record<Api["CaseResponse"]["status"], MatterStatus> = {
  draft: "active",
  open: "active",
  on_hold: "on_hold",
  closed: "closed",
};

function toMatter(row: Api["CaseResponse"], hearings: HearingRow[] = [], isLead = false): Matter {
  return {
    id: row.id,
    title: same(row.title),
    clientId: "",
    // Case responses carry no client name (clients are linked by invitation).
    clientName: same("—"),
    court: same(row.court ?? ""),
    caseType: same(row.case_type),
    hearingNumber: row.hearing_count ?? hearings.length,
    status: STATUS[row.status],
    nextHearing: nextHearingOf(hearings),
    // Derived by the backend from hearings and status; never a hand-set stage.
    progress: row.progress,
    archived: Boolean(row.archived_at),
    isLead,
  };
}

export async function listMatters(includeArchived = false): Promise<Matter[]> {
  return withDemoFallback(
    async () =>
      (await backend<Api["CaseResponse"][]>(`/api/v1/cases${includeArchived ? "?include_archived=true" : ""}`)).map(
        (row) => toMatter(row),
      ),
    () => demo.listMatters(includeArchived),
  );
}

export async function getCase(caseId: string): Promise<Matter | null> {
  return withDemoFallback(
    async () => {
      const row = await backendOrNull<Api["CaseResponse"]>(`/api/v1/cases/${encodeURIComponent(caseId)}`);
      if (!row) return null;
      const [hearings, members, session] = await Promise.all([
        backendOrNull<HearingRow[]>(caseUrl(caseId, "/hearings")),
        backendOrNull<Api["CaseMemberResponse"][]>(`/api/v1/cases/${encodeURIComponent(caseId)}/members`),
        getSession(),
      ]);
      const me = session?.user?.id;
      const isLead = Boolean(me && members?.some((m) => m.user_id === me && m.role === "lead_lawyer"));
      return toMatter(row, hearings ?? [], isLead);
    },
    () => demo.getCase(caseId),
  );
}

/**
 * Edit title, case type, court and status. Active/on hold go through PATCH;
 * closing and reopening use the dedicated endpoints (client access changes).
 * Every step is audit-logged by the backend.
 */
export async function editMatter(caseId: string, input: EditMatterInput): Promise<EditMatterResult> {
  const title = input.title.trim();
  const caseType = input.caseType.trim();
  const court = input.court.trim();
  if (!title || title.length > 300 || !caseType || caseType.length > 100 || court.length > 200) return "invalid";
  return withDemoFallback<EditMatterResult>(
    async () => {
      const url = `/api/v1/cases/${encodeURIComponent(caseId)}`;
      try {
        const current = await backend<Api["CaseResponse"]>(url);
        if (current.archived_at) return "archived";
        const changed =
          title !== current.title || caseType !== current.case_type || (court || null) !== (current.court ?? null);
        // Closed cases are read-only: only a status change (reopen) is allowed.
        if (current.status === "closed" && input.status === "closed") return changed ? "closed" : "ok";
        if (current.status === "closed" && input.status !== "closed") {
          await backend(`${url}/reopen`, { method: "POST" });
        }
        await backend<Api["CaseResponse"]>(url, {
          method: "PATCH",
          json: {
            title,
            case_type: caseType,
            court: court || null,
            ...(input.status === "closed" ? {} : { status: input.status === "on_hold" ? "on_hold" : "open" }),
          } satisfies Api["CasePatch"],
        });
        if (current.status !== "closed" && input.status === "closed") {
          await backend(`${url}/close`, { method: "POST", json: {} satisfies Api["CaseCloseRequest"] });
        }
        return "ok";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        return error.status === 422 ? "invalid" : "error";
      }
    },
    () => (demo.editMatter(caseId, { title, caseType, court, status: input.status }) ? "ok" : "error"),
  );
}

/** Soft delete (archive) or restore. Lead lawyer only; nothing is deleted. */
export async function setMatterArchived(caseId: string, archived: boolean): Promise<boolean> {
  return withDemoFallback(
    async () => {
      try {
        await backend<Api["CaseResponse"]>(
          `/api/v1/cases/${encodeURIComponent(caseId)}/${archived ? "archive" : "restore"}`,
          { method: "POST" },
        );
        return true;
      } catch (error) {
        if (error instanceof BackendError) return false;
        throw error;
      }
    },
    () => demo.setArchived(caseId, archived),
  );
}

export async function getRecentMatters(limit = 3): Promise<Matter[]> {
  return (await listMatters()).filter((matter) => matter.status === "active").slice(0, limit);
}

// ---------- hearings ----------

function toHearings(
  matter: Matter,
  rows: HearingRow[],
  timeline: TimelineRow[],
  reassessments: Reassessment[],
): Hearing[] {
  return sortHearings(rows).map((row, index) => {
    const updates = timeline
      .filter((entry) => entry.hearing_id === row.id)
      .map((entry) => ({
        id: entry.hearing_update_id,
        text: [entry.order_text, entry.notes].filter(Boolean).join("\n"),
      }));
    const purpose = row.purpose ? { id: `${row.id}-purpose`, text: row.purpose } : null;
    // Full history for the timeline (every append-only version is kept).
    const notes = [...(purpose ? [purpose] : []), ...updates];
    const reassessment = reassessments.find((item) => item.hearingId === row.id);
    return {
      id: row.id,
      number: index + 1,
      date: (row.scheduled_at ?? row.created_at).slice(0, 10),
      court: matter.court,
      notes: notes.length > 0 ? notes : [{ id: `${row.id}-empty`, text: "" }],
      keyNotes: currentKeyNotes(purpose, updates),
      summaryStatus: !reassessment
        ? "none"
        : reassessment.clientUpdateStatus === "published"
          ? "approved"
          : "draft_ready",
    };
  });
}

export async function listHearings(caseId: string): Promise<Hearing[]> {
  return withDemoFallback(
    async () => {
      const [matter, rows, timeline, reassessments] = await Promise.all([
        getCase(caseId),
        backend<HearingRow[]>(caseUrl(caseId, "/hearings")),
        backend<TimelineRow[]>(caseUrl(caseId, "/hearings/timeline")),
        listReassessments(caseId),
      ]);
      return matter ? toHearings(matter, rows, timeline, reassessments) : [];
    },
    () => demo.listHearings(caseId),
  );
}

function isValidDate(date: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const parsed = new Date(`${date}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date;
}

/** The lawyer typed this date, so it is lawyer-confirmed (Rule 5). */
export async function addHearing(caseId: string, input: NewHearingInput): Promise<boolean> {
  const note = input.note.trim();
  if (!isValidDate(input.date) || !note) return false;
  return withDemoFallback(
    async () => {
      try {
        await backend<HearingRow>(caseUrl(caseId, "/hearings"), {
          method: "POST",
          json: {
            scheduled_at: `${input.date}T10:00:00+06:00`,
            purpose: note.slice(0, 300),
            date_confirmed: true,
          } satisfies Api["HearingCreate"],
        });
        return true;
      } catch (error) {
        if (error instanceof BackendError) return false;
        throw error;
      }
    },
    () => demo.addHearing(caseId, input) !== null,
  );
}

/**
 * Record a hearing outcome: the backend appends it to the timeline and re-runs
 * analysis and strategy. A next date is confirmed only when the lawyer says so.
 */
export async function submitHearingUpdate(
  caseId: string,
  hearingId: string,
  input: HearingUpdateInput,
): Promise<ActionResult> {
  const orderText = input.orderText.trim();
  if (!orderText) return { status: "error", message: "order_text" };
  if (input.nextHearingConfirmed && !input.nextHearingDate) {
    return { status: "error", message: "next_date" };
  }
  return mutate(() =>
    backend<ReassessmentRow>(caseUrl(caseId, `/hearings/${encodeURIComponent(hearingId)}/updates`), {
      method: "POST",
      json: {
        order_text: orderText,
        notes: input.notes.trim() || null,
        next_hearing_date: input.nextHearingDate ? `${input.nextHearingDate}T10:00:00+06:00` : null,
        next_hearing_confirmed: input.nextHearingConfirmed,
      } satisfies Api["HearingUpdateCreate"],
    }),
  );
}

/** Mock-only: notes in the demo data. Real notes are hearing updates (submitHearingUpdate). */
export async function addHearingNote(caseId: string, hearingId: string, text: string): Promise<boolean> {
  return withDemoFallback(
    async () => false,
    () => demo.addHearingNote(caseId, hearingId, text) !== null,
  );
}

// ---------- documents ----------

const DOCUMENT_STATUS: Record<Api["DocumentResponse"]["processing_status"], DocumentStatus> = {
  queued: "processing",
  processing: "processing",
  ready: "ready",
  needs_review: "ready",
  failed: "failed",
  deleted: "failed",
};

/** The backend does not link documents to hearings: show each under the latest hearing held by its upload date. */
function hearingFor(uploadedAt: string, hearings: Hearing[]): string {
  const day = uploadedAt.slice(0, 10);
  const earlier = hearings.filter((hearing) => hearing.date <= day);
  return (earlier[earlier.length - 1] ?? hearings[0])?.id ?? "";
}

function toDocument(row: Api["DocumentResponse"], hearings: Hearing[]): CaseDocument {
  return {
    id: row.id,
    hearingId: hearingFor(row.uploaded_at, hearings),
    name: row.original_filename,
    size: row.size_bytes,
    mimeType: row.mime_type,
    status: DOCUMENT_STATUS[row.processing_status],
  };
}

export async function listDocuments(caseId: string, hearings: Hearing[]): Promise<CaseDocument[]> {
  return withDemoFallback(
    async () => {
      const [rows, shares] = await Promise.all([
        backend<Api["DocumentResponse"][]>(caseUrl(caseId, "/documents")),
        backend<Api["SharedDocumentOut"][]>(`/api/v1/cases/${encodeURIComponent(caseId)}/shared-documents`),
      ]);
      const shared = new Set(shares.filter((row) => !row.revoked_at).map((row) => row.document_id));
      return rows.map((row) => ({ ...toDocument(row, hearings), sharedWithClient: shared.has(row.id) }));
    },
    () => demo.listDocuments(caseId),
  );
}

/** Upload one file; the backend validates, stores, scans and extracts it. */
export async function uploadDocument(
  caseId: string,
  hearingId: string,
  file: File,
): Promise<CaseDocument | null> {
  return withDemoFallback(
    async () => {
      const form = new FormData();
      form.append("file", file, file.name);
      try {
        const result = await backend<Api["UploadResponse"]>(caseUrl(caseId, "/documents"), {
          method: "POST",
          form,
        });
        return { ...toDocument(result.document, []), hearingId };
      } catch (error) {
        if (error instanceof BackendError) return null;
        throw error;
      }
    },
    () =>
      demo.addDocument(caseId, {
        hearingId,
        name: file.name,
        size: file.size,
        mimeType: file.type,
      }),
  );
}

/** Share a document with the client or stop sharing it (audit-logged by the backend). */
export async function setDocumentShared(caseId: string, documentId: string, share: boolean): Promise<ActionResult> {
  if (!caseId || !documentId) return { status: "error", message: "document" };
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/shared-documents`;
  return mutate(() =>
    share
      ? backend(base, { method: "POST", json: { document_id: documentId } satisfies Api["SharedDocumentCreate"] })
      : backend(`${base}/${encodeURIComponent(documentId)}`, { method: "DELETE" }),
  );
}

/** Real documents report their own status; only demo documents can be set. */
export async function getDocumentStatus(
  caseId: string,
  documentId: string,
  demoStatus: DocumentStatus,
): Promise<DocumentStatus | null> {
  return withDemoFallback(
    async () => {
      const row = await backendOrNull<Api["DocumentResponse"]>(
        caseUrl(caseId, `/documents/${encodeURIComponent(documentId)}`),
      );
      return row ? DOCUMENT_STATUS[row.processing_status] : null;
    },
    () => (demo.setDocumentStatus(caseId, documentId, demoStatus) ? demoStatus : null),
  );
}

// ---------- facts, analysis, strategy, reassessment ----------

function toFact(row: Api["FactOut"]): CaseFact {
  return {
    id: row.id,
    statement: row.statement,
    category: row.category as CaseFact["category"],
    statementType: row.statement_type as CaseFact["statementType"],
    review: row.review_status as CaseFact["review"],
    aiMock: row.origin === "ai_mock",
    usableInAnalysis: row.usable_in_analysis,
    sources: row.sources.map((source) => ({
      documentId: source.document_id,
      page: source.page_no,
      quote: source.quote,
      verification: verification(source.quote_check === "passed"),
    })),
  };
}

function toCitation(row: Api["CitationOut"]): Citation {
  return {
    act: row.act_title ?? "",
    section: row.section ?? "",
    quote: row.quote,
    url: row.source_url,
    verification: verification(row.verified),
    inForce: row.in_force_status,
  };
}

function toAnalysis(row: Api["AnalysisOut"]): CaseAnalysis {
  return {
    id: row.id,
    version: row.version,
    status: row.status,
    aiMock: row.origin === "ai_mock",
    provider: row.provider,
    // Backend KEYWORD_ONLY_WARNING: semantic search was unavailable for this run.
    keywordOnly: row.warnings.some((warning) => warning.startsWith("keyword_only_fallback")),
    createdAt: row.created_at,
    findings: row.findings.map((finding) => ({
      claim: finding.offence_or_claim,
      strength: finding.strength,
      verification: finding.verification,
      citation: toCitation(finding.section_citation),
      elements: finding.elements.map((element) => ({
        element: element.element,
        status: element.status,
        verification: verification(element.verified),
        factId: element.matched_fact_id,
      })),
      reasons: finding.reasons,
    })),
    missingInformation: row.missing_information,
    abstainReason: row.abstain_reason,
    precedentNote: row.precedent_note,
    warnings: row.warnings,
  };
}

function toMove(node: Api["StrategyNode"]): StrategyMove {
  return {
    id: node.id,
    actor: node.actor,
    move: node.move,
    legalBasis: node.legal_basis.map(toCitation),
    requirements: node.requirements,
    risk: node.risk,
    cost: node.cost,
    time: node.time,
    strength: node.strength,
    reasons: node.reasons,
    verification: verification(node.verified),
    children: node.children.map(toMove),
  };
}

function toStrategy(row: Api["StrategyOut"]): StrategyTree {
  return {
    id: row.id,
    version: row.version,
    analysisVersion: row.analysis_version,
    status: row.status,
    aiMock: row.origin === "ai_mock",
    provider: row.provider,
    createdAt: row.created_at,
    moves: row.root.children.map(toMove),
    missingInformation: row.missing_information,
    precedentNote: row.precedent_note,
    warnings: row.warnings,
  };
}

function toReassessment(row: ReassessmentRow): Reassessment {
  return {
    id: row.id,
    hearingId: row.hearing_id,
    changes: row.changes.map((change) => ({
      claim: change.offence_or_claim,
      before: strengthOf(change.before),
      after: strengthOf(change.after),
    })),
    closedOptions: row.closed_options,
    newOptions: row.new_options,
    treeVersion: row.tree_version,
    analysisVersion: row.analysis_version,
    tasks: row.tasks,
    suggestedNextDate: row.suggested_next_date ?? null,
    nextHearingId: row.next_hearing_id,
    clientUpdateId: row.client_update_id,
    clientUpdateStatus: row.client_update_status,
    createdAt: row.created_at,
  };
}

async function listReassessments(caseId: string): Promise<Reassessment[]> {
  return (await backend<ReassessmentRow[]>(caseUrl(caseId, "/reassessments"))).map(toReassessment);
}

const EMPTY_INTELLIGENCE: CaseIntelligence = {
  facts: [],
  analysis: null,
  strategy: null,
  reassessments: [],
};

/** Facts, latest analysis, latest strategy tree and reassessments for the matter workspace. */
export async function getCaseIntelligence(caseId: string): Promise<CaseIntelligence> {
  return withDemoFallback(
    async () => {
      const [facts, analysis, strategy, reassessments] = await Promise.all([
        backend<Api["FactOut"][]>(caseUrl(caseId, "/facts")),
        backendOrNull<Api["AnalysisOut"]>(caseUrl(caseId, "/analysis")),
        backendOrNull<Api["StrategyOut"]>(caseUrl(caseId, "/strategy")),
        listReassessments(caseId),
      ]);
      return {
        facts: facts.map(toFact),
        analysis: analysis ? toAnalysis(analysis) : null,
        strategy: strategy ? toStrategy(strategy) : null,
        reassessments,
      };
    },
    () => EMPTY_INTELLIGENCE,
  );
}

/** Run a backend mutation; demo mode cannot run AI, so it reports NOT_CONFIGURED. */
async function mutate(call: () => Promise<unknown>): Promise<ActionResult> {
  return withDemoFallback<ActionResult>(
    async () => {
      try {
        await call();
        return { status: "ok" };
      } catch (error) {
        if (error instanceof BackendError) {
          return error.status === 503
            ? { status: "NOT_CONFIGURED" }
            : { status: "error", message: error.detail };
        }
        throw error;
      }
    },
    () => ({ status: "NOT_CONFIGURED" }),
  );
}

export async function addFact(caseId: string, input: NewFactInput): Promise<ActionResult> {
  const statement = input.statement.trim();
  if (!statement) return { status: "error", message: "statement" };
  return mutate(() =>
    backend(caseUrl(caseId, "/facts"), {
      method: "POST",
      json: {
        category: input.category,
        statement,
        statement_type: "lawyer_entered",
        fact_status: "undisputed",
      } satisfies Api["FactCreateRequest"],
    }),
  );
}

export async function confirmFact(caseId: string, factId: string): Promise<ActionResult> {
  return mutate(() =>
    backend(caseUrl(caseId, `/facts/${encodeURIComponent(factId)}/confirm`), {
      method: "POST",
      json: {} satisfies Api["FactReviewRequest"],
    }),
  );
}

/**
 * Fix a fact whose quote was not found: a new version (never an overwrite) with
 * the corrected statement and quote; the backend re-checks the quote on the page.
 */
export async function editFact(caseId: string, factId: string, input: EditFactInput): Promise<ActionResult> {
  const statement = input.statement.trim();
  const quote = input.quote.trim();
  if (!statement || statement.length > 4000) return { status: "error", message: "statement" };
  if (!quote || quote.length > 2000 || !input.documentId || !(input.page >= 1)) {
    return { status: "error", message: "quote" };
  }
  return mutate(() =>
    backend(caseUrl(caseId, `/facts/${encodeURIComponent(factId)}`), {
      method: "PATCH",
      json: {
        statement,
        sources: [{ document_id: input.documentId, page_no: input.page, quote }],
      } satisfies Api["FactEditRequest"],
    }),
  );
}

export async function rejectFact(caseId: string, factId: string, note: string): Promise<ActionResult> {
  if (!note.trim()) return { status: "error", message: "note" };
  return mutate(() =>
    backend(caseUrl(caseId, `/facts/${encodeURIComponent(factId)}/reject`), {
      method: "POST",
      json: { note: note.trim() } satisfies Api["FactRejectRequest"],
    }),
  );
}

export async function extractFacts(caseId: string): Promise<ActionResult> {
  return mutate(() =>
    backend(caseUrl(caseId, "/facts/extractions"), {
      method: "POST",
      json: {} satisfies Api["ExtractionRequest"],
    }),
  );
}

export async function runAnalysis(caseId: string): Promise<ActionResult> {
  return mutate(() =>
    backend(caseUrl(caseId, "/analysis"), { method: "POST", json: {} satisfies Api["AnalysisRequest"] }),
  );
}

export async function runStrategy(caseId: string): Promise<ActionResult> {
  return mutate(() =>
    backend(caseUrl(caseId, "/strategy"), { method: "POST", json: {} satisfies Api["StrategyRequest"] }),
  );
}

// ---------- hearing summary (lawyer review before the client sees it) ----------

function claim(
  id: string,
  type: SummaryClaim["type"],
  verified: Verification,
  text: string,
  source: Localized,
): SummaryClaim {
  return { id, type, verification: verified, text: same(text), source };
}

const SOURCES = {
  hearing: { en: "Hearing record (lawyer entered)", bn: "শুনানির রেকর্ড (আইনজীবী প্রদত্ত)" },
  analysis: { en: "AI analysis (draft for review)", bn: "এআই বিশ্লেষণ (পর্যালোচনার খসড়া)" },
  strategy: { en: "Strategy tree (draft for review)", bn: "কৌশল বৃক্ষ (পর্যালোচনার খসড়া)" },
  tasks: { en: "Reassessment tasks", bn: "পুনর্মূল্যায়নের কাজ" },
};

function summarySections(
  hearing: Hearing,
  reassessment: Reassessment,
  analysis: CaseAnalysis | null,
): SummarySection[] {
  // Current notes only: superseded update versions are history, not extra key notes.
  const keyNotes = (hearing.keyNotes ?? currentKeyNotes(null, hearing.notes)).map((note) =>
    claim(`note-${note.id}`, "lawyer", "verified", note.text, SOURCES.hearing),
  );
  const laws = (analysis?.findings ?? []).map((finding, index) =>
    claim(
      `finding-${index}`,
      "ai",
      finding.verification,
      `${finding.claim} — ${finding.strength}`,
      same(`${finding.citation.act} s. ${finding.citation.section}`.trim()),
    ),
  );
  const risks = [
    ...reassessment.closedOptions.map((option, index) =>
      claim(`closed-${index}`, "ai", "unverified", option, SOURCES.strategy),
    ),
    ...reassessment.changes.map((change, index) =>
      claim(
        `change-${index}`,
        "ai",
        "unverified",
        `${change.claim}: ${change.before ?? "—"} → ${change.after ?? "—"}`,
        SOURCES.analysis,
      ),
    ),
  ];
  const rights = reassessment.newOptions.map((option, index) =>
    claim(`option-${index}`, "ai", "unverified", option, SOURCES.strategy),
  );
  const notes = analysis?.precedentNote
    ? [claim("precedent", "ai", "verified", analysis.precedentNote, SOURCES.analysis)]
    : [];
  const nextSteps = reassessment.tasks.map((task, index) =>
    claim(`task-${index}`, "ai", "unverified", task, SOURCES.tasks),
  );
  const sections: SummarySection[] = [
    { id: "keyNotes", claims: keyNotes },
    { id: "laws", claims: laws },
    { id: "risks", claims: risks },
    { id: "rights", claims: rights },
    { id: "notes", claims: notes },
    { id: "nextSteps", claims: nextSteps },
  ];
  return sections.filter((section) => section.claims.length > 0);
}

const LAWYER_EDIT: Localized = { en: "Lawyer edit", bn: "আইনজীবীর সম্পাদনা" };

function summaryVersionsUrl(caseId: string, hearingId: string) {
  return caseUrl(caseId, `/hearings/${encodeURIComponent(hearingId)}/summary-versions`);
}

async function realSummary(caseId: string, hearingId: string): Promise<HearingSummary | null> {
  const [matter, hearings, reassessments, saved, session] = await Promise.all([
    getCase(caseId),
    listHearings(caseId),
    listReassessments(caseId),
    backend<Api["SummaryVersionOut"][]>(summaryVersionsUrl(caseId, hearingId)),
    getSession(),
  ]);
  const hearing = hearings.find((item) => item.id === hearingId);
  const reassessment = reassessments.find((item) => item.hearingId === hearingId);
  if (!matter || !hearing || !reassessment) return null;

  const analysisRow = await backendOrNull<Api["AnalysisOut"]>(
    caseUrl(caseId, `/analysis/versions/${reassessment.analysisVersion}`),
  );
  const sections = summarySections(hearing, reassessment, analysisRow ? toAnalysis(analysisRow) : null);
  const me = session?.user;
  const versions = [
    {
      id: reassessment.id,
      version: 1,
      createdAt: reassessment.createdAt,
      editedBy: { en: "AI draft", bn: "এআই খসড়া" },
      sections,
    },
    // Lawyer edits: append-only versions stored by the backend (Rule 6).
    ...saved.map((row) => ({
      id: row.id,
      version: row.version,
      createdAt: row.created_at,
      editedBy: me && row.created_by === me.id ? same(me.full_name || me.email) : LAWYER_EDIT,
      sections: row.sections,
    })),
  ];
  const latest = versions[versions.length - 1];
  return {
    caseId,
    hearingId,
    hearingNumber: hearing.number,
    hearingDate: hearing.date,
    court: hearing.court,
    matterTitle: matter.title,
    clientName: matter.clientName,
    status: hearing.summaryStatus,
    version: latest.version,
    sections: latest.sections,
    versions,
  };
}

export async function getHearingSummary(caseId: string, hearingId: string): Promise<HearingSummary | null> {
  return withDemoFallback(
    () => realSummary(caseId, hearingId),
    () => demo.getHearingSummary(caseId, hearingId),
  );
}

export type SaveSummaryResult = "ok" | "stale" | "error";

/**
 * Save the lawyer's edit as a new version (never an overwrite). baseVersion is
 * the version the editor was opened on; a newer saved version makes this
 * "stale" so a concurrent edit is never silently replaced.
 */
export async function saveHearingSummaryVersion(
  caseId: string,
  hearingId: string,
  baseVersion: number,
  sections: SummarySection[],
): Promise<SaveSummaryResult> {
  return withDemoFallback<SaveSummaryResult>(
    async () => {
      try {
        await backend<Api["SummaryVersionOut"]>(summaryVersionsUrl(caseId, hearingId), {
          method: "POST",
          json: { base_version: baseVersion, sections } satisfies Api["SummaryVersionCreate"],
        });
        return "ok";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        return error.status === 409 ? "stale" : "error";
      }
    },
    () => (demo.saveHearingSummaryVersion(caseId, hearingId, sections) !== null ? "ok" : "error"),
  );
}

/** Lawyer approval publishes the draft client update for this hearing (Rule 8). */
export async function approveHearingSummary(caseId: string, hearingId: string): Promise<boolean> {
  return withDemoFallback(
    async () => {
      const reassessment = (await listReassessments(caseId)).find((item) => item.hearingId === hearingId);
      if (!reassessment?.clientUpdateId) return false;
      if (reassessment.clientUpdateStatus === "published") return true;
      try {
        await backend(`/api/v1/client-updates/${encodeURIComponent(reassessment.clientUpdateId)}/publish`, {
          method: "POST",
        });
        return true;
      } catch (error) {
        if (error instanceof BackendError) return false;
        throw error;
      }
    },
    () => demo.approveHearingSummary(caseId, hearingId) !== null,
  );
}

/**
 * The summary as a PDF rendered by the backend (embedded Noto Sans / Noto Sans
 * Bengali). The content is exactly what the lawyer sees, with each claim's
 * statement type, verification and source; returns null when there is no
 * summary, NOT_CONFIGURED in demo mode.
 */
export async function downloadHearingSummaryPdf(
  caseId: string,
  hearingId: string,
  language: Language,
): Promise<{ pdf: Response } | null | "NOT_CONFIGURED"> {
  const token = await sessionToken();
  if (!token) return "NOT_CONFIGURED";
  const summary = await getHearingSummary(caseId, hearingId);
  if (!summary) return null;
  const copy = dictionaries[language].hearingSummary;
  const statusLabels = dictionaries[language].caseDetail.summary;
  const profile = await getLawyerProfile();
  const body: Api["SummaryPdfRequest"] = {
    eyebrow: copy.eyebrow,
    title: `${format(copy.title, { number: numberFor(language, summary.hearingNumber) })} · ${format(
      copy.versionLabel,
      { number: numberFor(language, summary.version) },
    )}`,
    meta: [
      { label: copy.matter, value: pick(summary.matterTitle, language) },
      { label: copy.client, value: pick(summary.clientName, language) },
      { label: copy.court, value: pick(summary.court, language) },
      { label: copy.hearingDate, value: summary.hearingDate },
      { label: copy.preparedBy, value: pick(profile.name, language) },
      { label: copy.status, value: statusLabels[summary.status] },
    ],
    notice: copy.notLegalAdvice,
    sections: summary.sections.map((section) => ({
      heading: copy.sections[section.id],
      items: section.claims.map((claim) => ({
        text: pick(claim.text, language) || claim.text.en || claim.text.bn,
        tags: [copy.claimTypes[claim.type], claim.verification === "verified" ? copy.verified : copy.unverified],
        source: `${copy.source}: ${pick(claim.source, language) || claim.source.en}`,
      })),
    })),
    footer: copy.notLegalAdvice,
    filename: `hearing-${summary.hearingNumber}-summary-v${summary.version}.pdf`,
  };
  const pdf = await backendRequest(
    caseUrl(caseId, `/hearings/${encodeURIComponent(hearingId)}/summary-pdf`),
    { method: "POST", json: body, token },
  );
  if (pdf.status === 404) return null;
  if (!pdf.ok) throw new BackendError(pdf.status, pdf.statusText);
  return { pdf };
}

// ---------- clients ----------

function toClient(row: Api["ClientResponse"]) {
  return { id: row.id, name: same(row.display_name), phone: row.phone ?? "", email: row.email ?? "" };
}

export async function listClients(): Promise<ClientSummary[]> {
  return withDemoFallback(
    async () =>
      (await backend<Api["ClientResponse"][]>("/api/v1/clients")).map((row) => ({
        ...toClient(row),
        caseCount: 0,
      })),
    () => demo.listClients(),
  );
}

export async function getClientDetail(clientId: string): Promise<ClientDetail | null> {
  return withDemoFallback(
    async () => {
      const row = await backendOrNull<Api["ClientResponse"]>(`/api/v1/clients/${encodeURIComponent(clientId)}`);
      return row ? { ...toClient(row), cases: [] } : null;
    },
    () => demo.getClientDetail(clientId),
  );
}

export type LinkableClient = { id: string; name: string };
export type LinkClientResult = "ok" | "no_login" | "error" | "NOT_CONFIGURED";

/** Clients with a portal login: only they can be given access to a case. */
export async function listLinkableClients(): Promise<LinkableClient[]> {
  return withDemoFallback(
    async () =>
      (await backend<Api["ClientResponse"][]>("/api/v1/clients"))
        .filter((row) => row.has_account)
        .map((row) => ({ id: row.id, name: row.email ? `${row.display_name} (${row.email})` : row.display_name })),
    () => [],
  );
}

/** Make an existing client a member (role client) of a case the lawyer leads. */
export async function linkClientToCase(caseId: string, clientId: string): Promise<LinkClientResult> {
  if (!caseId || !clientId) return "error";
  return withDemoFallback<LinkClientResult>(
    async () => {
      try {
        await backend<Api["ClientCaseLinkResponse"]>(
          `/api/v1/clients/${encodeURIComponent(clientId)}/cases`,
          { method: "POST", json: { case_id: caseId } satisfies Api["ClientCaseLinkCreate"] },
        );
        return "ok";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        return error.status === 400 ? "no_login" : "error";
      }
    },
    () => "NOT_CONFIGURED",
  );
}

/**
 * Create the client and, with an email, their portal login. The backend returns
 * the temporary password once; it is passed straight to the lawyer's screen.
 */
export async function createClient(
  input: NewClientInput,
): Promise<ClientCredentials | { error: CreateClientError }> {
  const name = input.name.trim();
  const email = input.email.trim();
  if (!name || !/\S+@\S+\.\S+/.test(email)) return { error: "invalid" };
  if (input.password && input.password.length < 12) return { error: "password" };
  return withDemoFallback<ClientCredentials | { error: CreateClientError }>(
    async () => {
      try {
        const row = await backend<Api["ClientCreatedResponse"]>("/api/v1/clients", {
          method: "POST",
          json: {
            display_name: name,
            email,
            phone: input.phone.trim() || null,
            password: input.password || null,
            case_id: input.caseId || null,
          } satisfies Api["ClientCreate"],
        });
        if (!row.temporary_password || !row.email) return { error: "general" };
        const linked = row.linked_case_id
          ? (await listMatters()).find((matter) => matter.id === row.linked_case_id)
          : undefined;
        return {
          name: row.display_name,
          email: row.email,
          password: row.temporary_password,
          linkedCaseTitle: linked ? linked.title.en : null,
        };
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        if (error.status === 409) return { error: "email_taken" };
        if (error.status === 404) return { error: "case" };
        if (error.status === 422) return { error: "invalid" };
        return { error: "general" };
      }
    },
    () => demo.createClient(input) ?? { error: "invalid" },
  );
}

/** New temporary password for a client; the backend signs the client out everywhere. */
export async function resetClientPassword(clientId: string): Promise<ResetPasswordState> {
  return withDemoFallback<ResetPasswordState>(
    async () => {
      try {
        const row = await backend<Api["ClientPasswordResetResponse"]>(
          `/api/v1/clients/${encodeURIComponent(clientId)}/password-reset`,
          { method: "POST" },
        );
        return { status: "ok", email: row.email, password: row.temporary_password };
      } catch (error) {
        if (error instanceof BackendError) return { status: "error" };
        throw error;
      }
    },
    () => demo.resetClientPassword(),
  );
}

export async function createMatter(input: NewMatterInput): Promise<boolean> {
  const title = input.title.trim();
  if (!title || !input.caseType) return false;
  return withDemoFallback(
    async () => {
      try {
        await backend<Api["CaseResponse"]>("/api/v1/cases", {
          method: "POST",
          json: {
            reference_no: `LC-${Date.now().toString(36).toUpperCase()}`,
            title,
            case_type: input.caseType,
            court: input.court || null,
          } satisfies Api["CaseCreate"],
        });
        return true;
      } catch (error) {
        if (error instanceof BackendError) return false;
        throw error;
      }
    },
    () => demo.createMatter(input) !== null,
  );
}

// ---------- dashboard and profile ----------

export async function getLawyerStats(): Promise<LawyerStats> {
  return withDemoFallback(
    async () => {
      const overview = await backend<Api["LawyerOverviewResponse"]>("/api/v1/lawyer/dashboard/overview");
      return {
        activeCases: overview.active_cases,
        totalMatters: overview.total_matters,
        totalClients: overview.total_clients,
        nextHearing: null,
      };
    },
    () => demo.getLawyerStats(),
  );
}

function activityIcon(objectType: string | null): Activity["icon"] {
  if (objectType === "document") return "document";
  if (objectType === "hearing" || objectType === "case_reassessment") return "calendar";
  return "clients";
}

export async function getRecentActivity(): Promise<Activity[]> {
  return withDemoFallback(
    async () =>
      (await backend<Api["LawyerActivityResponse"][]>("/api/v1/lawyer/dashboard/activity")).map((row) => ({
        id: row.id,
        icon: activityIcon(row.object_type),
        title: same(row.action.replaceAll(".", " ").replaceAll("_", " ")),
        detail: same(row.object_type?.replaceAll("_", " ") ?? ""),
        time: dateParts(row.occurred_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }),
      })),
    () => demo.getRecentActivity(),
  );
}

function toProfileDetail(row: Api["LawyerProfileResponse"]): LawyerProfileDetail {
  return {
    fullName: row.full_name,
    email: row.email,
    phone: row.phone ?? "",
    preferredLanguage: row.preferred_language,
    chamberName: row.chamber_name ?? "",
    organizationName: row.organization_name,
    canEditOrganization: row.can_edit_organization,
    visibleFields: row.client_visible_fields,
    photoId: row.photo_id ?? null,
    barEnrollmentNo: row.bar_enrollment_no ?? "",
    courts: row.courts,
    practiceAreas: row.practice_areas,
    yearsExperience: row.years_experience ?? null,
    officeAddress: row.office_address ?? "",
    languages: row.languages,
    bio: row.bio ?? "",
    publicPhone: row.public_phone ?? "",
    publicEmail: row.public_email ?? "",
  };
}

/** Editable profile fields; null in demo mode (profile edit needs the backend). */
export async function getLawyerProfileDetail(): Promise<LawyerProfileDetail | null> {
  return withDemoFallback<LawyerProfileDetail | null>(
    async () => toProfileDetail(await backend<Api["LawyerProfileResponse"]>("/api/v1/lawyer/profile")),
    () => null,
  );
}

export type ProfileResult = "ok" | "invalid" | "error" | "NOT_CONFIGURED";

/** Update the profile (audit-logged by the backend). Email is never sent. */
export async function updateLawyerProfile(input: ProfileInput, canEditOrganization: boolean): Promise<ProfileResult> {
  if (!isValidProfileInput(input, canEditOrganization)) return "invalid";
  const text = (value: string) => nfc(value) || null;
  return withDemoFallback<ProfileResult>(
    async () => {
      try {
        await backend<Api["LawyerProfileResponse"]>("/api/v1/lawyer/profile", {
          method: "PATCH",
          json: {
            full_name: nfc(input.fullName),
            phone: input.phone.trim() || null,
            preferred_language: input.preferredLanguage,
            chamber_name: text(input.chamberName),
            bar_enrollment_no: text(input.barEnrollmentNo),
            courts: input.courts.map(nfc).filter(Boolean),
            practice_areas: input.practiceAreas,
            years_experience: input.yearsExperience,
            office_address: text(input.officeAddress),
            languages: input.languages,
            bio: text(input.bio),
            public_phone: input.publicPhone.trim() ? normalizeBdPhone(input.publicPhone) : null,
            public_email: input.publicEmail.trim() || null,
            client_visible_fields: input.visibleFields,
            ...(canEditOrganization ? { organization_name: nfc(input.organizationName) } : {}),
          } satisfies Api["LawyerProfilePatch"],
        });
        return "ok";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        return error.status === 422 ? "invalid" : "error";
      }
    },
    () => "NOT_CONFIGURED",
  );
}

export async function getLawyerProfile(): Promise<LawyerProfile> {
  const session = await getSession();
  const user = session?.user;
  if (!user) return demo.getLawyerProfile();
  const detail = await getLawyerProfileDetail();
  const name = detail?.fullName || user.full_name || user.email;
  return {
    firstName: same(name.split(" ")[0]),
    name: same(name),
    email: user.email,
    firm: same(detail ? detail.chamberName || detail.organizationName : ""),
    location: same(""),
    photoId: detail?.photoId ?? null,
  };
}

// Option lists for the new-matter form (reference vocabulary, not case data).
export function listCourts(): Localized[] {
  return demo.listCourts();
}

export function listCaseTypes(): Localized[] {
  return demo.listCaseTypes();
}
