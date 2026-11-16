import {
  clientCase,
  clientProfile,
  storedSummaries,
} from "@/lib/mock/client";

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

function approvedSummaries(): ClientSummary[] {
  return storedSummaries
    .filter((summary) => summary.status === "approved")
    .map(({ id, title, excerpt, publishedOn }) => ({
      id,
      title,
      excerpt,
      publishedOn,
    }));
}

export function getClientProfile(): ClientProfile {
  return clientProfile;
}

export function getClientCase(): ClientCase {
  return { ...clientCase, summaries: approvedSummaries() };
}

export function getApprovedSummary(summaryId: string): ClientSummary | null {
  return approvedSummaries().find((summary) => summary.id === summaryId) ?? null;
}
