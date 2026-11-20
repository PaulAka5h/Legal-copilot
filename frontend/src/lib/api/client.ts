import "server-only";

import {
  backend,
  backendOrNull,
  withDemoFallback,
  type Api,
} from "@/lib/api/backendClient";
import {
  clientCase,
  clientProfile,
  storedSummaries,
} from "@/lib/mock/client";
import { getSession } from "@/lib/session";

/*
 * Client portal data. The client reads only client-visible data (Rule 8):
 * published updates, shared documents and the confirmed next hearing, through
 * /api/v1/client/... . When the backend is unreachable the demo data is shown
 * with a demo-data label.
 */

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

function same(text: string | null | undefined): Localized {
  const value = text ?? "";
  return { en: value, bn: value };
}

function dateLabel(iso: string, options: Intl.DateTimeFormatOptions): Localized {
  const date = new Date(iso);
  return {
    en: new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", ...options }).format(date),
    bn: new Intl.DateTimeFormat("bn-BD", { timeZone: "Asia/Dhaka", ...options }).format(date),
  };
}

const DAY_MONTH_YEAR: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" };
const EXCERPT_CHARS = 180;

function toSummary(row: Api["app__client_portal__schemas__ClientUpdateResponse"]): ClientSummary {
  const excerpt = row.body.length > EXCERPT_CHARS ? `${row.body.slice(0, EXCERPT_CHARS)}…` : row.body;
  return {
    id: row.id,
    title: same(row.title),
    excerpt: same(excerpt),
    publishedOn: row.published_at ? dateLabel(row.published_at, DAY_MONTH_YEAR) : same(""),
  };
}

function toNextHearing(
  row: Api["ClientHearingResponse"] | null,
  court: string | null,
): NextHearing | null {
  if (!row?.scheduled_at) return null;
  const date = new Date(row.scheduled_at);
  const part = (option: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", ...option }).format(date);
  return {
    day: Number(part({ day: "numeric" })),
    month: dateLabel(row.scheduled_at, { month: "short" }),
    year: Number(part({ year: "numeric" })),
    place: same(row.court_room ?? court ?? ""),
    dateLabel: dateLabel(row.scheduled_at, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }),
  };
}

/** The backend keeps no client-visible stage, so only the first stage is shown as current. */
function stagesFor(closed: boolean): CaseStage[] {
  return clientCase.stages.map((stage, index) => ({
    ...stage,
    note: same(""),
    state: closed ? "complete" : index === 0 ? "current" : "upcoming",
  }));
}

async function myCases(): Promise<Api["ClientCaseResponse"][]> {
  return backend<Api["ClientCaseResponse"][]>("/api/v1/client/cases");
}

function clientCaseUrl(caseId: string, suffix: string) {
  return `/api/v1/client/cases/${encodeURIComponent(caseId)}${suffix}`;
}

export async function getClientProfile(): Promise<ClientProfile> {
  const user = (await getSession())?.user;
  return user ? { name: same(user.full_name || user.email) } : clientProfile;
}

export async function getClientCase(): Promise<ClientCase | null> {
  return withDemoFallback(
    async () => {
      const [row] = await myCases();
      if (!row) return null;
      const [hearing, documents, updates] = await Promise.all([
        backendOrNull<Api["ClientHearingResponse"] | null>(clientCaseUrl(row.id, "/hearing")),
        backend<Api["ClientDocumentResponse"][]>(clientCaseUrl(row.id, "/documents")),
        backend<Api["app__client_portal__schemas__ClientUpdateResponse"][]>(clientCaseUrl(row.id, "/updates")),
      ]);
      const closed = row.status === "closed";
      return {
        id: row.id,
        title: same(row.title),
        statusLabel: closed ? { en: "Closed", bn: "নিষ্পন্ন" } : { en: "Active", bn: "সক্রিয়" },
        caseType: same(row.case_type),
        court: same(row.court ?? ""),
        hearingNumber: updates.length,
        stages: stagesFor(closed),
        nextHearing: toNextHearing(hearing, row.court ?? null),
        // Lawyer contact details are not exposed to clients by the API yet.
        lawyer: {
          name: { en: "Your lawyer", bn: "আপনার আইনজীবী" },
          firm: same(""),
          phone: "",
          email: "",
        },
        documents: documents.map((document) => ({
          id: document.id,
          format: "PDF" as const,
          name: same(document.display_name),
          size: same(""),
          sharedOn: dateLabel(document.shared_at, DAY_MONTH_YEAR),
        })),
        summaries: updates.map(toSummary),
      };
    },
    () => ({ ...clientCase, summaries: approvedSummaries() }),
  );
}

export async function getApprovedSummary(summaryId: string): Promise<ClientSummaryDetail | null> {
  return withDemoFallback(
    async () => {
      for (const row of await myCases()) {
        const updates = await backend<Api["app__client_portal__schemas__ClientUpdateResponse"][]>(
          clientCaseUrl(row.id, "/updates"),
        );
        const update = updates.find((item) => item.id === summaryId);
        if (update) {
          const summary = toSummary(update);
          const [, ...rest] = defaultSections(summary);
          return { ...summary, sections: [{ id: "keyNotes", text: same(update.body) }, ...rest] };
        }
      }
      return null;
    },
    () => demoSummary(summaryId),
  );
}

function demoSummary(summaryId: string): ClientSummaryDetail | null {
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
