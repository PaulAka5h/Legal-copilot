import { NextResponse } from "next/server";
import { downloadHearingSummaryPdf } from "@/lib/api/lawyer";
import { fileResponse } from "@/lib/fileResponse";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

/** The hearing summary as a server-rendered PDF attachment (lawyers on the case only). */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ caseId: string; hearingId: string }> },
) {
  const session = await getSession();
  if (!session || session.role !== "lawyer") {
    return NextResponse.redirect(new URL("/lawyer/login", request.url));
  }
  const { caseId, hearingId } = await params;
  const summaryPath = `/lawyer/matters/${encodeURIComponent(caseId)}/hearings/${encodeURIComponent(hearingId)}/summary`;
  const result = await downloadHearingSummaryPdf(caseId, hearingId, await getLanguage());
  if (result === "NOT_CONFIGURED") {
    return NextResponse.redirect(new URL(`${summaryPath}?download=NOT_CONFIGURED#download`, request.url));
  }
  if (result === null) return new NextResponse("Not found", { status: 404 });
  return fileResponse(result.pdf);
}
