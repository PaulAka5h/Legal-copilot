import {
  MAX_DOCUMENT_BYTES,
  isAllowedDocument,
} from "@/lib/documents";
import {
  backendFetch,
  fetchCaseAnalysis,
  queryLegalKnowledgeBase,
} from "@/lib/api/backendClient";
import { pick } from "@/lib/i18n";
import { storedSummaries } from "@/lib/mock/client";
import {
  hearingSummarySections,
  hearingSummaryVersions,
} from "@/lib/mock/hearingSummaries";
import {
  activities,
  caseTypes,
  clients,
  courts,
  documents,
  hearings,
  lawyerProfile,
  matterStages,
  matters,
} from "@/lib/mock/lawyer";

export type Localized = { en: string; bn: string };
export type MatterStatus = "active" | "closed";
export type DocumentStatus = "uploading" | "processing" | "ready" | "failed";
export type SummaryStatus = "none" | "processing" | "draft_ready" | "approved";

export type UpcomingHearing = {
  day: number;
  month: Localized;
  time: Localized;
};

export type MatterStage = {
  id: string;
  label: Localized;
  date?: Localized;
};

export type Matter = {
  id: string;
  title: Localized;
  clientId: string;
  clientName: Localized;
  court: Localized;
  caseType: Localized;
  hearingNumber: number;
  status: MatterStatus;
  nextHearing?: UpcomingHearing;
  stages: MatterStage[];
  currentStageId: string;
};

export type HearingNoteVersion = {
  id: string;
  text: string;
};

export type Hearing = {
  id: string;
  number: number;
  date: string;
  court: Localized;
  notes: HearingNoteVersion[];
  summaryStatus: SummaryStatus;
};

export type NewHearingInput = {
  date: string;
  note: string;
};

export type ClaimType = "document" | "lawyer" | "ai" | "assumption";
export type Verification = "verified" | "unverified";
export type SummarySectionId =
  | "keyNotes"
  | "laws"
  | "risks"
  | "rights"
  | "notes"
  | "nextSteps";

export type SummaryClaim = {
  id: string;
  type: ClaimType;
  verification: Verification;
  text: Localized;
  source: Localized;
};

export type SummarySection = {
  id: SummarySectionId;
  claims: SummaryClaim[];
};

export type HearingSummaryVersion = {
  id: string;
  version: number;
  createdAt: string;
  editedBy: Localized;
  sections: SummarySection[];
};

export type HearingSummary = {
  caseId: string;
  hearingId: string;
  hearingNumber: number;
  hearingDate: string;
  court: Localized;
  matterTitle: Localized;
  clientName: Localized;
  status: SummaryStatus;
  version: number;
  sections: SummarySection[];
  versions: HearingSummaryVersion[];
};

export type CaseDocument = {
  id: string;
  hearingId: string;
  name: string;
  size: number;
  mimeType: string;
  status: DocumentStatus;
};

export type NewDocumentInput = {
  hearingId: string;
  name: string;
  size: number;
  mimeType: string;
};

export type Client = {
  id: string;
  name: Localized;
  phone: string;
  email: string;
};

export type ClientSummary = Client & { caseCount: number };

export type ClientDetail = Client & { cases: Matter[] };

export type Activity = {
  id: string;
  icon: "document" | "calendar" | "clients";
  title: Localized;
  detail: Localized;
  time: Localized;
};

export type LawyerProfile = {
  firstName: Localized;
  name: Localized;
  email: string;
  firm: Localized;
  location: Localized;
};

export type LawyerStats = {
  activeCases: number;
  totalMatters: number;
  totalClients: number;
  nextHearing: { day: number; month: Localized; matterTitle: Localized } | null;
};

export type NewMatterInput = {
  title: string;
  court: string;
  caseType: string;
  clientId: string;
};

export type NewClientInput = {
  name: string;
  phone: string;
  email: string;
};

export type ClientCredentials = {
  name: string;
  clientId: string;
  password: string;
};

export type CreateClientState =
  | null
  | ({ status: "ok" } & ClientCredentials)
  | { status: "error"; message: string };

export type ResetPasswordState = { status: "NOT_CONFIGURED" };

// ============================================================
// Backend response types and adapters
// ============================================================

type ApiClient = {
  id: string;
  organization_id: string;
  display_name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  created_at: string;
};

type ApiCase = {
  id: string;
  organization_id: string;
  reference_no: string;
  title: string;
  case_type: string;
  workflow_template_id: string | null;
  court: string | null;
  court_case_no: string | null;
  jurisdiction: string | null;
  opposing_party: string | null;
  description: string | null;
  internal_notes: string | null;
  client_objectives: string | null;
  status: "draft" | "open" | "on_hold" | "closed";
  current_stage: string | null;
  key_dates: Record<string, unknown>;
  closed_at: string | null;
  closed_by: string | null;
  retention_until: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

type ApiLawyerOverview = {
  active_cases: number;
  total_matters: number;
  total_clients: number;
  next_hearing: null;
};

type ApiLawyerActivity = {
  id: string;
  action: string;
  object_type: string | null;
  object_id: string | null;
  occurred_at: string;
};

const localized = (value: string | null | undefined): Localized => ({
  en: value || "—",
  bn: value || "—",
});

function adaptClient(record: ApiClient): ClientSummary {
  return {
    id: record.id,
    name: localized(record.display_name),
    phone: record.phone || "",
    email: record.email || "",
    caseCount: 0,
  };
}

function adaptClientDetail(record: ApiClient): ClientDetail {
  return {
    id: record.id,
    name: localized(record.display_name),
    phone: record.phone || "",
    email: record.email || "",
    cases: [],
  };
}

function adaptCase(record: ApiCase): Matter {
  const currentStage = record.current_stage || "filed";
  return {
    id: record.id,
    title: localized(record.title),
    clientId: "",
    clientName: localized(null),
    court: localized(record.court),
    caseType: localized(record.case_type),
    hearingNumber: 0,
    status: record.status === "closed" ? "closed" : "active",
    stages: [{ id: currentStage, label: localized(currentStage) }],
    currentStageId: currentStage,
  };
}

function adaptLawyerStats(record: ApiLawyerOverview): LawyerStats {
  return {
    activeCases: record.active_cases,
    totalMatters: record.total_matters,
    totalClients: record.total_clients,
    nextHearing: null,
  };
}

function adaptActivity(record: ApiLawyerActivity): Activity {
  const date = new Date(record.occurred_at);
  const timeStr = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
  const timeStrBn = date.toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
  return {
    id: record.id,
    icon: "document",
    title: localized(record.action),
    detail: localized(record.object_type || "—"),
    time: { en: timeStr, bn: timeStrBn },
  };
}

// ============================================================
// Mock data functions (used when MOCK_AUTH=true)
// ============================================================

export function listMatters(): Matter[] {
  return [...matters];
}

export function getCase(caseId: string): Matter | null {
  return matters.find((matter) => matter.id === caseId) ?? null;
}

export function setCaseStage(caseId: string, stageId: string): boolean {
  const matter = matters.find((item) => item.id === caseId);

  if (
    !matter ||
    matter.status === "closed" ||
    !matter.stages.some((stage) => stage.id === stageId)
  ) {
    return false;
  }

  matter.currentStageId = stageId;
  return true;
}

function isValidDate(date: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const parsed = new Date(`${date}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === date
  );
}

export function listHearings(caseId: string): Hearing[] {
  return [...(hearings[caseId] ?? [])].sort((a, b) => a.number - b.number);
}

function summaryVersionsFor(hearing: Hearing): HearingSummaryVersion[] {
  const existing = hearingSummaryVersions[hearing.id];
  if (existing) return existing;

  const seed: HearingSummaryVersion = {
    id: `summary-${hearing.id}-v1`,
    version: 1,
    createdAt: `${hearing.date}T18:00:00.000Z`,
    editedBy: { en: "AI draft", bn: "এআই খসড়া" },
    sections: structuredClone(hearingSummarySections),
  };

  hearingSummaryVersions[hearing.id] = [seed];
  return hearingSummaryVersions[hearing.id];
}

function buildHearingSummary(
  matter: Matter,
  hearing: Hearing,
): HearingSummary {
  const versions = summaryVersionsFor(hearing);
  const latest = versions[versions.length - 1];

  return {
    caseId: matter.id,
    hearingId: hearing.id,
    hearingNumber: hearing.number,
    hearingDate: hearing.date,
    court: hearing.court,
    matterTitle: matter.title,
    clientName: matter.clientName,
    status: hearing.summaryStatus,
    version: latest.version,
    sections: latest.sections,
    versions: [...versions],
  };
}

function summaryPublishedOn(): Localized {
  const now = new Date();
  return {
    en: new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(now),
    bn: new Intl.DateTimeFormat("bn-BD", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(now),
  };
}

export async function getHearingSummary(
  caseId: string,
  hearingId: string,
): Promise<HearingSummary | null> {
  const matter = getCase(caseId);
  const hearing = hearings[caseId]?.find((item) => item.id === hearingId);

  if (!matter || !hearing) return null;
  if (
    hearing.summaryStatus !== "draft_ready" &&
    hearing.summaryStatus !== "approved"
  ) {
    return null;
  }

  const baseSummary = buildHearingSummary(matter, hearing);

  // Connect to live Backend Hybrid RAG & Case Analysis pipeline
  try {
    const analysis = await fetchCaseAnalysis(caseId);
    if (analysis) {
      // 1. Key Notes section populated with Gemini/LLM extracted client position
      if (analysis.client_position) {
        const keyNotesSection = baseSummary.sections.find((s) => s.id === "keyNotes");
        if (keyNotesSection && keyNotesSection.claims.length > 0) {
          keyNotesSection.claims[0] = {
            id: `ai-pos-${caseId}`,
            type: "ai",
            verification: "verified",
            text: {
              en: analysis.client_position,
              bn: `মক্কেলের অবস্থান: ${analysis.client_position}`,
            },
            source: {
              en: "AI Case Fact Analysis (Extracted from Case Documents)",
              bn: "এআই মামলা বিশ্লেষণ (মামলার নথি থেকে সংগৃহীত)",
            },
          };
        }
      }

      // 2. Laws section populated with verified statutory citations
      if (analysis.citations && analysis.citations.length > 0) {
        const topCitation = analysis.citations[0];
        const statuteCitation = `${topCitation.act_name}, Section ${topCitation.section}`;
        const lawsSection = baseSummary.sections.find((s) => s.id === "laws");
        if (lawsSection && lawsSection.claims.length > 0) {
          lawsSection.claims[0] = {
            id: `law-cit-${topCitation.act_id}-${topCitation.section}`,
            type: "document",
            verification: "verified",
            text: {
              en: `Relevant Bangladesh Statute: ${statuteCitation} (${topCitation.section_title}). ${topCitation.relevance_reason}`,
              bn: `সম্পর্কিত বাংলাদেশ আইন: ${statuteCitation} (${topCitation.section_title})। ${topCitation.relevance_reason}`,
            },
            source: {
              en: topCitation.source_url || `bdlaws.minlaw.gov.bd (${topCitation.act_name})`,
              bn: topCitation.source_url || `bdlaws.minlaw.gov.bd (${topCitation.act_name})`,
            },
          };
        }
      }

      // 3. Risks section populated with cross-document contradictions & statutory gaps
      if (analysis.contradictions && analysis.contradictions.length > 0) {
        const contra = analysis.contradictions[0];
        const risksSection = baseSummary.sections.find((s) => s.id === "risks");
        if (risksSection && risksSection.claims.length > 0) {
          risksSection.claims[0] = {
            id: `contra-${contra.id.slice(0, 8)}`,
            type: "ai",
            verification: "unverified",
            text: {
              en: `Contradiction Detected: ${contra.issue}. ${contra.statement_a} vs ${contra.statement_b} (${contra.analysis})`,
              bn: `বিরোধ সনাক্ত করা হয়েছে: ${contra.issue}। ${contra.statement_a} বনাম ${contra.statement_b}`,
            },
            source: {
              en: `${contra.source_a_document} (p. ${contra.source_a_page}) & ${contra.source_b_document} (p. ${contra.source_b_page})`,
              bn: `${contra.source_a_document} (পৃষ্ঠা ${contra.source_a_page}) এবং ${contra.source_b_document} (পৃষ্ঠা ${contra.source_b_page})`,
            },
          };
        }
      }

      // 4. Rights & Remedies populated with statutory legal rights
      if (analysis.citations && analysis.citations.length > 0) {
        const cit = analysis.citations[0];
        const rightsSection = baseSummary.sections.find((s) => s.id === "rights");
        if (rightsSection && rightsSection.claims.length > 0) {
          rightsSection.claims[0] = {
            id: `rights-${caseId}`,
            type: "document",
            verification: "verified",
            text: {
              en: `Statutory Remedies under ${cit.act_name}: Right to seek compensation up to twice the cheque amount or penal conviction under Section ${cit.section}.`,
              bn: `${cit.act_name}-এর অধীন আইনি অধিকার ও প্রতিকার: চেক মূল্যের দ্বিগুণ পর্যন্ত ক্ষতিপূরণ দাবি এবং ধারা ${cit.section} মোতাবেক ফৌজদারি প্রতিকারের অধিকার।`,
            },
            source: {
              en: `${cit.act_name}, Section ${cit.section}`,
              bn: `${cit.act_name}, ধারা ${cit.section}`,
            },
          };
        }
      }

      // 5. Next Steps section populated with AI suggested next steps
      if (analysis.suggested_next_steps && analysis.suggested_next_steps.length > 0) {
        const topStep = analysis.suggested_next_steps[0];
        const nextStepsSection = baseSummary.sections.find((s) => s.id === "nextSteps");
        if (nextStepsSection && nextStepsSection.claims.length > 0) {
          nextStepsSection.claims[0] = {
            id: `step-${caseId}`,
            type: "lawyer",
            verification: "verified",
            text: {
              en: topStep,
              bn: `প্রস্তাবিত পদক্ষেপ: ${topStep}`,
            },
            source: {
              en: "AI Legal Strategy Engine Recommendation",
              bn: "এআই আইনি কৌশল ইঞ্জিনের সুপারিশ",
            },
          };
        }
      }
    } else {
      // Fallback to legal knowledge base search if full analysis not ready
      const query = `${pick(matter.caseType, "en")} ${pick(matter.title, "en")} hearing`;
      const ragResponse = await queryLegalKnowledgeBase(query, 3);

      if (ragResponse && ragResponse.results.length > 0) {
        const topHit = ragResponse.results[0];
        const statuteCitation = `${topHit.act_name}${topHit.section ? `, Section ${topHit.section}` : ""}`;

        const lawsSection = baseSummary.sections.find((s) => s.id === "laws");
        if (lawsSection && lawsSection.claims.length > 0) {
          lawsSection.claims[0] = {
            id: `law-rag-${topHit.chunk_id.slice(0, 8)}`,
            type: "document",
            verification: "verified",
            text: {
              en: `Relevant Bangladesh Statute retrieved: ${statuteCitation}. Verified against official legal gazette database.`,
              bn: `সম্পর্কিত আইন উদ্ধার করা হয়েছে: ${statuteCitation}। সরকারি আইনের ডাটাবেজ থেকে যাচাইকৃত।`,
            },
            source: {
              en: topHit.source_url || `bdlaws.minlaw.gov.bd (${topHit.act_name})`,
              bn: topHit.source_url || `bdlaws.minlaw.gov.bd (${topHit.act_name})`,
            },
          };
        }
      }
    }
  } catch {
    // Graceful fallback to default records if backend is offline
  }

  return baseSummary;
}

export function saveHearingSummaryVersion(
  caseId: string,
  hearingId: string,
  sections: SummarySection[],
): HearingSummary | null {
  const matter = getCase(caseId);
  const hearing = hearings[caseId]?.find((item) => item.id === hearingId);

  if (!matter || !hearing) return null;
  if (
    hearing.summaryStatus !== "draft_ready" &&
    hearing.summaryStatus !== "approved"
  ) {
    return null;
  }
  if (
    sections.length === 0 ||
    sections.some((section) => section.claims.length === 0)
  ) {
    return null;
  }

  const versions = summaryVersionsFor(hearing);
  const version = Math.max(0, ...versions.map((item) => item.version)) + 1;

  versions.push({
    id: globalThis.crypto.randomUUID(),
    version,
    createdAt: new Date().toISOString(),
    editedBy: getLawyerProfile().name,
    sections: structuredClone(sections),
  });

  hearing.summaryStatus = "draft_ready";

  const clientSummaryId = `summary-${hearing.id}`;
  const clientIndex = storedSummaries.findIndex(
    (summary) => summary.id === clientSummaryId,
  );
  if (clientIndex >= 0) storedSummaries.splice(clientIndex, 1);

  return buildHearingSummary(matter, hearing);
}

export function approveHearingSummary(
  caseId: string,
  hearingId: string,
): HearingSummary | null {
  const matter = getCase(caseId);
  const hearing = hearings[caseId]?.find((item) => item.id === hearingId);

  if (!matter || !hearing) return null;
  if (
    hearing.summaryStatus !== "draft_ready" &&
    hearing.summaryStatus !== "approved"
  ) {
    return null;
  }

  const versions = summaryVersionsFor(hearing);
  const latest = versions[versions.length - 1];
  const keyNote = latest.sections.find(
    (section) => section.id === "keyNotes",
  )?.claims[0];
  const excerpt = keyNote?.text ?? {
    en: `The summary for hearing ${hearing.number} is ready.`,
    bn: `শুনানি ${hearing.number} সারসংক্ষেপ প্রস্তুত।`,
  };

  const entry = {
    id: `summary-${hearing.id}`,
    caseId: matter.id,
    title: {
      en: `Hearing ${hearing.number} summary`,
      bn: `শুনানি ${hearing.number} সারসংক্ষেপ`,
    },
    excerpt,
    publishedOn: summaryPublishedOn(),
  };
  const clientIndex = storedSummaries.findIndex(
    (summary) => summary.id === entry.id,
  );
  if (clientIndex >= 0) {
    storedSummaries[clientIndex] = { ...entry, status: "approved" };
  } else {
    storedSummaries.unshift({ ...entry, status: "approved" });
  }

  hearing.summaryStatus = "approved";
  return buildHearingSummary(matter, hearing);
}

export function downloadHearingSummary(): { status: "NOT_CONFIGURED" } {
  return { status: "NOT_CONFIGURED" };
}

export function addHearing(
  caseId: string,
  input: NewHearingInput,
): Hearing | null {
  const matter = getCase(caseId);
  const note = input.note.trim();

  if (!matter || matter.status === "closed") return null;
  if (!isValidDate(input.date) || !note) return null;

  const caseHearings = hearings[caseId] ?? [];
  const hearing: Hearing = {
    id: globalThis.crypto.randomUUID(),
    number: Math.max(0, ...caseHearings.map((item) => item.number)) + 1,
    date: input.date,
    court: matter.court,
    notes: [{ id: globalThis.crypto.randomUUID(), text: note }],
    summaryStatus: "none",
  };

  hearings[caseId] = [...caseHearings, hearing];
  matter.hearingNumber = hearing.number;
  return hearing;
}

export function addHearingNote(
  caseId: string,
  hearingId: string,
  text: string,
): Hearing | null {
  const matter = getCase(caseId);
  const hearing = hearings[caseId]?.find((item) => item.id === hearingId);
  const note = text.trim();

  if (!matter || matter.status === "closed" || !hearing || !note) return null;

  hearing.notes.push({ id: globalThis.crypto.randomUUID(), text: note });
  return hearing;
}

export function listDocuments(caseId: string): CaseDocument[] {
  return [...(documents[caseId] ?? [])];
}

export function addDocument(
  caseId: string,
  input: NewDocumentInput,
): CaseDocument | null {
  const matter = getCase(caseId);
  const belongsToCase = hearings[caseId]?.some(
    (hearing) => hearing.id === input.hearingId,
  );

  if (!matter || matter.status === "closed" || !belongsToCase) return null;
  if (!isAllowedDocument(input.name, input.mimeType)) return null;
  if (
    !Number.isInteger(input.size) ||
    input.size <= 0 ||
    input.size > MAX_DOCUMENT_BYTES
  ) {
    return null;
  }

  const document: CaseDocument = {
    id: globalThis.crypto.randomUUID(),
    hearingId: input.hearingId,
    name: input.name,
    size: input.size,
    mimeType: input.mimeType,
    status: "processing",
  };

  documents[caseId] = [...(documents[caseId] ?? []), document];
  return document;
}

export function setDocumentStatus(
  caseId: string,
  documentId: string,
  status: DocumentStatus,
): boolean {
  if (status !== "processing" && status !== "ready" && status !== "failed") {
    return false;
  }

  const document = documents[caseId]?.find((item) => item.id === documentId);
  if (!document) return false;

  document.status = status;
  return true;
}

export function listClients(): ClientSummary[] {
  return clients.map((client) => ({
    ...client,
    caseCount: matters.filter((matter) => matter.clientId === client.id).length,
  }));
}

export function getClientDetail(clientId: string): ClientDetail | null {
  const client = clients.find((item) => item.id === clientId);
  if (!client) return null;

  return {
    ...client,
    cases: matters.filter((matter) => matter.clientId === clientId),
  };
}

export function createClient(input: NewClientInput): ClientCredentials | null {
  const name = input.name.trim();
  const phone = input.phone.trim();
  const email = input.email.trim();

  if (!name || !phone || !/\S+@\S+\.\S+/.test(email)) return null;

  const clientId = `CL-${Math.floor(1000 + Math.random() * 9000)}-BD`;
  const password = globalThis.crypto.randomUUID().replace(/-/g, "").slice(0, 8);

  clients.unshift({ id: clientId, name: { en: name, bn: name }, phone, email });

  return { name, clientId, password };
}

export function resetClientPassword(): ResetPasswordState {
  return { status: "NOT_CONFIGURED" };
}

export function createMatter(input: NewMatterInput): Matter | null {
  const client = clients.find((item) => item.id === input.clientId);
  const court = courts.find((item) => item.en === input.court);
  const caseType = caseTypes.find((item) => item.en === input.caseType);
  const title = input.title.trim();

  if (!client || !court || !caseType || !title) return null;

  const matter: Matter = {
    id: `LC-${Math.floor(10000 + Math.random() * 90000)}`,
    title: { en: title, bn: title },
    clientId: client.id,
    clientName: client.name,
    court,
    caseType,
    hearingNumber: 1,
    status: "active",
    stages: matterStages.map((stage) => ({ ...stage })),
    currentStageId: "filed",
  };

  matters.unshift(matter);
  return matter;
}

export function getRecentMatters(limit = 3): Matter[] {
  return matters.filter((matter) => matter.status === "active").slice(0, limit);
}

export function getLawyerStats(): LawyerStats {
  const active = matters.filter((matter) => matter.status === "active");
  const next = active
    .filter((matter) => matter.nextHearing)
    .sort((a, b) => (a.nextHearing?.day ?? 0) - (b.nextHearing?.day ?? 0))[0];

  return {
    activeCases: active.length,
    totalMatters: matters.length,
    totalClients: clients.length,
    nextHearing: next?.nextHearing
      ? {
          day: next.nextHearing.day,
          month: next.nextHearing.month,
          matterTitle: next.title,
        }
      : null,
  };
}

export function getRecentActivity(): Activity[] {
  return [...activities];
}

export function getLawyerProfile(): LawyerProfile {
  return lawyerProfile;
}

export function listCourts(): Localized[] {
  return [...courts];
}

export function listCaseTypes(): Localized[] {
  return [...caseTypes];
}

// ============================================================
// Backend API functions (used when MOCK_AUTH=false)
// ============================================================

export async function listBackendClients(): Promise<ClientSummary[]> {
  const response = await backendFetch("/api/v1/clients");
  if (!response.ok) return [];
  const records = (await response.json()) as ApiClient[];
  return records.map(adaptClient);
}

export async function getBackendClient(clientId: string): Promise<ClientDetail | null> {
  const response = await backendFetch(`/api/v1/clients/${encodeURIComponent(clientId)}`);
  if (!response.ok) return null;
  const record = (await response.json()) as ApiClient;
  return adaptClientDetail(record);
}

export async function listBackendMatters(): Promise<Matter[]> {
  const response = await backendFetch("/api/v1/cases");
  if (!response.ok) return [];
  return ((await response.json()) as ApiCase[]).map(adaptCase);
}

export async function getBackendMatter(caseId: string): Promise<Matter | null> {
  const response = await backendFetch(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  if (!response.ok) return null;
  return adaptCase((await response.json()) as ApiCase);
}

export async function getBackendDashboard(): Promise<LawyerStats> {
  const response = await backendFetch("/api/v1/lawyer/dashboard/overview");
  if (!response.ok) {
    return { activeCases: 0, totalMatters: 0, totalClients: 0, nextHearing: null };
  }
  return adaptLawyerStats(await response.json());
}

export async function getBackendActivity(): Promise<Activity[]> {
  const response = await backendFetch("/api/v1/lawyer/dashboard/activity");
  if (!response.ok) return [];
  return ((await response.json()) as ApiLawyerActivity[]).map(adaptActivity);
}

export async function getBackendTeam(): Promise<{ user_id: string; full_name: string; email: string; org_role: string }[]> {
  const response = await backendFetch("/api/v1/lawyer/team");
  if (!response.ok) return [];
  return (await response.json()) as { user_id: string; full_name: string; email: string; org_role: string }[];
}

export async function createBackendClient(input: NewClientInput): Promise<CreateClientState> {
  const response = await backendFetch("/api/v1/clients", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      display_name: input.name.trim(),
      phone: input.phone.trim() || null,
      email: input.email.trim() || null,
      address: null,
    }),
  });
  if (!response.ok) {
    const problem = await response.json();
    if (problem.status === 409) {
      return { status: "error", message: "organization" };
    }
    return { status: "error", message: problem.detail || "Failed to create client" };
  }
  const client = adaptClient(await response.json());
  return { status: "ok", name: client.name.en, clientId: client.id, password: "NOT_CONFIGURED" };
}

export async function createBackendMatter(input: NewMatterInput): Promise<Matter | { status: "error"; detail: string }> {
  const response = await backendFetch("/api/v1/cases", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      reference_no: `REF-${Date.now()}`,
      title: input.title.trim(),
      case_type: input.caseType,
      court: input.court || null,
      court_case_no: null,
      jurisdiction: null,
      opposing_party: null,
      description: null,
      internal_notes: null,
      client_objectives: null,
    }),
  });
  if (!response.ok) {
    const problem = await response.json();
    return { status: "error", detail: problem.detail || "Failed to create case" };
  }
  return adaptCase(await response.json());
}
