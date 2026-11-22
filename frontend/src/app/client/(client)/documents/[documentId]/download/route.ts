import { NextResponse } from "next/server";
import { clientFile, documentDownloadPath } from "@/lib/api/client";
import { fileResponse } from "@/lib/fileResponse";
import { getSession } from "@/lib/session";

/** A document the lawyer shared with this client, proxied from the backend (authorized per case). */
export async function GET(request: Request, { params }: { params: Promise<{ documentId: string }> }) {
  const session = await getSession();
  if (!session || session.role !== "client" || session.passwordChangeRequired) {
    return NextResponse.redirect(new URL("/client/login", request.url));
  }
  const { documentId } = await params;
  const result = await clientFile(documentDownloadPath(documentId));
  if (result === "NOT_CONFIGURED") return NextResponse.redirect(new URL("/client/dashboard", request.url));
  if (result === null) return new NextResponse("Not found", { status: 404 });
  return fileResponse(result);
}
