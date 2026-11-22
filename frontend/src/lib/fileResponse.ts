import "server-only";

import { NextResponse } from "next/server";

/** Pass a backend file through as an attachment, keeping only safe headers. */
export function fileResponse(upstream: Response): NextResponse {
  const headers = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  for (const name of ["Content-Type", "Content-Disposition", "Content-Length"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new NextResponse(upstream.body, { status: 200, headers });
}
