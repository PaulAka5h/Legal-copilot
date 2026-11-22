import { NextResponse } from "next/server";
import { clientFile, summaryPdfPath } from "@/lib/api/client";
import { fileResponse } from "@/lib/fileResponse";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

/** An approved, client-visible summary as a server-rendered PDF (the backend authorizes per case). */
export async function GET(request: Request, { params }: { params: Promise<{ summaryId: string }> }) {
  const session = await getSession();
  if (!session || session.role !== "client" || session.passwordChangeRequired) {
    return NextResponse.redirect(new URL("/client/login", request.url));
  }
  const { summaryId } = await params;
  const result = await clientFile(summaryPdfPath(summaryId, await getLanguage()));
  if (result === "NOT_CONFIGURED") {
    return NextResponse.redirect(
      new URL(`/client/summaries/${encodeURIComponent(summaryId)}?download=NOT_CONFIGURED#download`, request.url),
    );
  }
  if (result === null) return new NextResponse("Not found", { status: 404 });
  return fileResponse(result);
}
