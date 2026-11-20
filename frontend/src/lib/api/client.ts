import {
  clientCase,
  clientProfile,
  storedSummaries,
} from "@/lib/mock/client";
import { backendFetch } from "@/lib/api/backendClient";

export type Localized = { en: string; bn: string };
export type StageState = "complete" | "current" | "upcoming";

export type ClientProfile = {
  name: Localized;
};

export type CaseStage = {
  id: string;
  label: Localized;
  note: Localized;
  state: StageState;
};

export type LawyerContact = {
  name: Localized;
  firm: Localized;
  phone: string;
  email: string;
};

export type NextHearing = {
  day: number;
  month: Localized;
  year: number;
  place: Localized;
  dateLabel: Localized;
};

export type SharedDocument = {
  id: string;
  format: "PDF";
  name: Localized;
  size: Localized;
  sharedOn: Localized;
};

export type ClientSummary = {
  id: string;
  title: Localized;
  excerpt: Localized;
  publishedOn: Localized;
};

export type ClientSummarySectionId =
  | "keyNotes"
  | "laws"
  | "risks"
  | "rights"
  | "notes"
  | "nextSteps";

export type ClientSummarySection = {
  id: ClientSummarySectionId;
  text: Localized;
};

export type ClientSummaryDetail = ClientSummary & {
  sections: ClientSummarySection[];
};

export type ClientCase = {
  id: string;
  title: Localized;
  statusLabel: Localized;
  caseType: Localized;
  court: Localized;
  hearingNumber: number;
  stages: CaseStage[];
  nextHearing: NextHearing | null;
  lawyer: LawyerContact;
  documents: SharedDocument[];
  summaries: ClientSummary[];
};

export type BackendClientCase = {
  id: string;
  title: string;
  status: "draft" | "open" | "on_hold" | "closed";
  case_type: string;
  court: string | null;
};

export type BackendClientHearing = {
  id: string;
  scheduled_at: string;
  purpose: string | null;
  court_room: string | null;
};

export type BackendClientDocument = {
  id: string;
  document_id: string;
  display_name: string;
  shared_at: string;
};

export type BackendClientUpdate = {
  id: string;
  version: number;
  title: string;
  body: string;
  language: "en" | "bn";
  published_at: string | null;
};

export type BackendClientTask = {
  id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  status: "open" | "done" | "cancelled";
};

export async function listBackendClientCases(): Promise<BackendClientCase[]> {
  const response = await backendFetch("/api/v1/client/cases");
  return response.ok ? (await response.json()) as BackendClientCase[] : [];
}

export async function fetchClientHearing(caseId: string): Promise<BackendClientHearing | null> {
  const response = await backendFetch(`/api/v1/client/cases/${encodeURIComponent(caseId)}/hearing`);
  if (!response.ok) return null;
  return (await response.json()) as BackendClientHearing | null;
}

export async function fetchClientDocuments(caseId: string): Promise<BackendClientDocument[]> {
  const response = await backendFetch(`/api/v1/client/cases/${encodeURIComponent(caseId)}/documents`);
  if (!response.ok) return [];
  return (await response.json()) as BackendClientDocument[];
}

export async function fetchClientUpdates(caseId: string): Promise<BackendClientUpdate[]> {
  const response = await backendFetch(`/api/v1/client/cases/${encodeURIComponent(caseId)}/updates`);
  if (!response.ok) return [];
  return (await response.json()) as BackendClientUpdate[];
}

export async function fetchClientTasks(caseId: string): Promise<BackendClientTask[]> {
  const response = await backendFetch(`/api/v1/client/cases/${encodeURIComponent(caseId)}/tasks`);
  if (!response.ok) return [];
  return (await response.json()) as BackendClientTask[];
}

function approvedSummaries(): ClientSummary[] {
  return storedSummaries
    .filter(
      (summary) =>
        summary.status === "approved" &&
        (summary.caseId ?? clientCase.id) === clientCase.id,
    )
    .map(({ id, title, excerpt, publishedOn }) => ({
      id,
      title,
      excerpt,
      publishedOn,
    }));
}

function defaultSections(summary: ClientSummary): ClientSummarySection[] {
  return [
    { id: "keyNotes", text: summary.excerpt },
    {
      id: "laws",
      text: {
        en: "No legal provision is shared in this update. Ask your lawyer if you need the legal basis explained.",
        bn: "এই আপডেটে কোনো আইনি ধারা শেয়ার করা হয়নি। আইনি ভিত্তি বুঝতে চাইলে আপনার আইনজীবীকে জিজ্ঞাসা করুন।",
      },
    },
    {
      id: "risks",
      text: {
        en: "Your lawyer has reviewed what this means for your case. Ask about anything that affects you.",
        bn: "এটি আপনার মামলার জন্য কী অর্থ বহন করে, আপনার আইনজীবী তা পর্যালোচনা করেছেন। আপনার ওপর প্রভাব ফেলে এমন কিছু থাকলে জিজ্ঞাসা করুন।",
      },
    },
    {
      id: "rights",
      text: {
        en: "You have the right to be kept informed and to ask your lawyer questions.",
        bn: "তথ্য জানার এবং আপনার আইনজীবীকে প্রশ্ন করার অধিকার আপনার আছে।",
      },
    },
    {
      id: "notes",
      text: {
        en: "This is a short update approved for you by your lawyer.",
        bn: "এটি আপনার আইনজীবীর অনুমোদিত একটি সংক্ষিপ্ত আপডেট।",
      },
    },
    {
      id: "nextSteps",
      text: {
        en: "Contact your lawyer if you need help with the next step.",
        bn: "পরবর্তী ধাপে সহায়তা প্রয়োজন হলে আপনার আইনজীবীর সাথে যোগাযোগ করুন।",
      },
    },
  ];
}

export function getClientProfile(): ClientProfile {
  return clientProfile;
}

export function getClientCase(): ClientCase {
  return { ...clientCase, summaries: approvedSummaries() };
}

export function getApprovedSummary(
  summaryId: string,
): ClientSummaryDetail | null {
  const summary = storedSummaries.find(
    (item) =>
      item.id === summaryId &&
      item.status === "approved" &&
      (item.caseId ?? clientCase.id) === clientCase.id,
  );

  if (!summary) return null;

  return {
    id: summary.id,
    title: summary.title,
    excerpt: summary.excerpt,
    publishedOn: summary.publishedOn,
    sections:
      summary.sections && summary.sections.length > 0
        ? summary.sections
        : defaultSections(summary),
  };
}

export function downloadClientSummary(): { status: "NOT_CONFIGURED" } {
  return { status: "NOT_CONFIGURED" };
}
