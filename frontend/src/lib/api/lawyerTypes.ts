/** UI data shapes for the lawyer portal. The API layer adapts backend responses to these. */

export type Localized = { en: string; bn: string };
export type MatterStatus = "active" | "on_hold" | "closed";
export type ProgressStageId = "opened" | "scheduled" | "held" | "closed";
export type ProgressState = "complete" | "current" | "upcoming";
/** Derived by the backend from hearings and case status (never hand-set). */
export type ProgressStage = { id: ProgressStageId; state: ProgressState };
export type DocumentStatus = "uploading" | "processing" | "ready" | "failed";
export type SummaryStatus = "none" | "processing" | "draft_ready" | "approved";

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
  progress: ProgressStage[];
  archived: boolean;
  /** The signed-in lawyer is the lead lawyer (only they may archive). */
  isLead: boolean;
};

export type EditMatterInput = {
  title: string;
  caseType: string;
  court: string;
  status: MatterStatus;
};

export type EditMatterResult = "ok" | "invalid" | "archived" | "closed" | "error" | "NOT_CONFIGURED";

export type LawyerProfileDetail = {
  fullName: string;
  email: string;
  phone: string;
  preferredLanguage: "en" | "bn";
  chamberName: string;
  organizationName: string;
  canEditOrganization: boolean;
  showContactToClients: boolean;
};

export type ProfileInput = {
  fullName: string;
  phone: string;
  preferredLanguage: "en" | "bn";
  chamberName: string;
  organizationName: string;
  showContactToClients: boolean;
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
  /** Current notes for the summary (latest update only, no repeats). Demo hearings omit it. */
  keyNotes?: HearingNoteVersion[];
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
  /** Shared with the client (lawyer's choice, default off). */
  sharedWithClient?: boolean;
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
  /** Empty: the backend generates a temporary password. */
  password: string;
  /** Empty: no case is linked. */
  caseId: string;
};

/** Shown to the lawyer once; never stored by the frontend. */
export type ClientCredentials = {
  name: string;
  email: string;
  password: string;
  linkedCaseTitle: string | null;
};

export type CreateClientError = "invalid" | "password" | "email_taken" | "case" | "general";

export type CreateClientState =
  | null
  | ({ status: "ok" } & ClientCredentials)
  | { status: "error"; reason: CreateClientError };

export type ResetPasswordState =
  | null
  | { status: "ok"; email: string; password: string }
  | { status: "error" }
  | { status: "NOT_CONFIGURED" };

// Case intelligence (Steps C–F). Statement types and strengths follow AGENTS.md Rules 3 and 4.
export type Strength = "strong" | "moderate" | "weak" | "insufficient";
export type Level = "low" | "medium" | "high" | "unknown";
export type StatementType =
  | "document_says"
  | "lawyer_entered"
  | "ai_inference"
  | "assumption";
export type FactCategory =
  | "party"
  | "date"
  | "place"
  | "act_or_omission"
  | "document"
  | "relief_sought"
  | "other";
export type FactReview = "draft" | "lawyer_reviewed" | "lawyer_rejected";

export type FactSource = {
  documentId: string | null;
  page: number | null;
  quote: string | null;
  verification: Verification;
};

export type CaseFact = {
  id: string;
  statement: string;
  category: FactCategory;
  statementType: StatementType;
  review: FactReview;
  aiMock: boolean;
  usableInAnalysis: boolean;
  sources: FactSource[];
};

export type EditFactInput = {
  statement: string;
  documentId: string;
  page: number;
  quote: string;
};

export type NewFactInput = {
  statement: string;
  category: FactCategory;
};

export type Citation = {
  act: string;
  section: string;
  quote: string | null;
  url: string | null;
  verification: Verification;
  inForce: string;
};

export type FindingElement = {
  element: string;
  status: "met" | "missing" | "disputed";
  verification: Verification;
  factId: string | null;
};

export type Finding = {
  claim: string;
  strength: Strength;
  verification: Verification;
  citation: Citation;
  elements: FindingElement[];
  reasons: string[];
};

export type CaseAnalysis = {
  id: string;
  version: number;
  status: "succeeded" | "insufficient_information" | "failed";
  aiMock: boolean;
  /** The provider that answered (gemini, groq, ...); "mock" for ai_mock output. */
  provider: string;
  keywordOnly: boolean;
  createdAt: string;
  findings: Finding[];
  missingInformation: string[];
  abstainReason: string | null;
  precedentNote: string;
  warnings: string[];
};

export type StrategyMove = {
  id: string;
  actor: "us" | "opponent" | "court";
  move: string;
  legalBasis: Citation[];
  requirements: string[];
  risk: Level;
  cost: Level;
  time: Level;
  strength: Strength;
  reasons: string[];
  verification: Verification;
  children: StrategyMove[];
};

export type StrategyTree = {
  id: string;
  version: number;
  analysisVersion: number;
  status: "succeeded" | "insufficient_information";
  aiMock: boolean;
  provider: string;
  createdAt: string;
  moves: StrategyMove[];
  missingInformation: string[];
  precedentNote: string;
  warnings: string[];
};

export type FindingChange = {
  claim: string;
  before: Strength | null;
  after: Strength | null;
};

export type ClientUpdateStatus = "draft" | "published" | "withdrawn";

export type Reassessment = {
  id: string;
  hearingId: string;
  changes: FindingChange[];
  closedOptions: string[];
  newOptions: string[];
  treeVersion: number | null;
  analysisVersion: number;
  tasks: string[];
  suggestedNextDate: string | null;
  nextHearingId: string | null;
  clientUpdateId: string | null;
  clientUpdateStatus: ClientUpdateStatus | null;
  createdAt: string;
};

export type HearingUpdateInput = {
  orderText: string;
  notes: string;
  nextHearingDate: string | null;
  nextHearingConfirmed: boolean;
};

export type CaseIntelligence = {
  facts: CaseFact[];
  analysis: CaseAnalysis | null;
  strategy: StrategyTree | null;
  reassessments: Reassessment[];
};

export type ActionResult =
  | { status: "ok" }
  | { status: "error"; message: string }
  | { status: "NOT_CONFIGURED" };
