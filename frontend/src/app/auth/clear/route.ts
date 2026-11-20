import { NextResponse } from "next/server";

export function GET(request: Request) {
  const url = new URL(request.url);
  const next = url.searchParams.get("next");
  const destination = next?.startsWith("/") && !next.startsWith("//") ? next : "/";
  const response = NextResponse.redirect(new URL(destination, url));
  response.cookies.set("lc_session", "", { httpOnly: true, maxAge: 0, path: "/", sameSite: "lax" });
  return response;
}
