/** Client for communicating with the PokkhoAI FastAPI backend (port 8000). */

const BACKEND_URL = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";

export type LegalSearchResult = {
  chunk_id: string;
  act_name: string;
  act_year?: string;
  section?: string;
  provision_label?: string;
  score: number;
  retrieval_type: string;
  text: string;
  source_url: string;
};

export type LegalSearchResponse = {
  query: string;
  total_results: number;
  results: LegalSearchResult[];
};

export async function queryLegalKnowledgeBase(
  query: string,
  topK = 5,
  actId?: string,
): Promise<LegalSearchResponse | null> {
  try {
    const params = new URLSearchParams({
      q: query,
      top_k: String(topK),
    });
    if (actId) params.append("act_id", actId);

    const res = await fetch(`${BACKEND_URL}/api/v1/legal-kb/search?${params.toString()}`, {
      method: "GET",
      cache: "no-store",
    });

    if (!res.ok) return null;
    return (await res.json()) as LegalSearchResponse;
  } catch (err) {
    console.error("Failed to query backend legal knowledge base:", err);
    return null;
  }
}

export type BackendTimelineEvent = {
  id: string;
  event_date: string;
  raw_date_text: string;
  title: string;
  description: string;
  actor: string;
  source_page: number;
  confidence: string;
  is_anomaly: boolean;
  anomaly_reason?: string;
};

export type BackendCaseAnalysis = {
  id: string;
  case_id: string;
  version: number;
  client_position: string;
  factual_summary: string;
  legal_issues: string[];
  claims: Array<{
    id: string;
    text: string;
    claim_type: string;
    confidence_label: string;
    needs_lawyer_review: boolean;
    sources: Array<{
      document_name: string;
      page_number: number;
      quote: string;
      source_url?: string;
    }>;
  }>;
  timeline: BackendTimelineEvent[];
  contradictions: Array<{
    id: string;
    issue: string;
    statement_a: string;
    source_a_document: string;
    source_a_page: number;
    statement_b: string;
    source_b_document: string;
    source_b_page: number;
    severity: string;
    analysis: string;
  }>;
  gaps: Array<{
    id: string;
    missing_item: string;
    statutory_requirement: string;
    impact: string;
  }>;
  citations: Array<{
    act_id: string;
    act_name: string;
    section: string;
    section_title: string;
    relevance_reason: string;
    source_url: string;
  }>;
  suggested_next_steps: string[];
  review_status: string;
};

export async function fetchCaseAnalysis(caseId: string): Promise<BackendCaseAnalysis | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/cases/${encodeURIComponent(caseId)}/analysis`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as BackendCaseAnalysis;
  } catch (err) {
    console.error("Failed to fetch backend case analysis:", err);
    return null;
  }
}

export async function fetchCaseTimeline(caseId: string): Promise<BackendTimelineEvent[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/cases/${encodeURIComponent(caseId)}/timeline`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return [];
    return (await res.json()) as BackendTimelineEvent[];
  } catch (err) {
    console.error("Failed to fetch backend case timeline:", err);
    return [];
  }
}
