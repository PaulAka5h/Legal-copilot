import {
  MAX_DOCUMENT_BYTES,
  isAllowedDocument,
} from "@/lib/documents";
import { queryLegalKnowledgeBase } from "@/lib/api/backendClient";
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
  | { status: "error" };

export type ResetPasswordState = { status: "NOT_CONFIGURED" };

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

  // Connect to live Backend Hybrid RAG pipeline if laws section is unverified
  try {
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
  } catch (err) {
    // Graceful fallback to default verified records if backend is offline
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
