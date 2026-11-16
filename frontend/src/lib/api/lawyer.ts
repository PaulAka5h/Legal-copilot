import {
  activities,
  caseTypes,
  clients,
  courts,
  lawyerProfile,
  matters,
} from "@/lib/mock/lawyer";

export type Localized = { en: string; bn: string };
export type MatterStatus = "active" | "closed";

export type UpcomingHearing = {
  day: number;
  month: Localized;
  time: Localized;
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
};

export type Client = {
  id: string;
  name: Localized;
  phone: string;
  email: string;
};

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

export function listMatters(): Matter[] {
  return [...matters];
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
