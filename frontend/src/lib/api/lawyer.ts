import {
  activities,
  caseTypes,
  clients,
  courts,
  lawyerProfile,
  matterStages,
  matters,
} from "@/lib/mock/lawyer";

export type Localized = { en: string; bn: string };
export type MatterStatus = "active" | "closed";

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
