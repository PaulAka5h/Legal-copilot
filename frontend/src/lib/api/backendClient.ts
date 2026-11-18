/** Client for communicating with Legal-Copilot FastAPI backend (port 8000). */

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
