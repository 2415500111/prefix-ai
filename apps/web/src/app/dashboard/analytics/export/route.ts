import { type NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/server/api";
import { getAccessToken } from "@/lib/server/session";

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Streams the procedure list as CSV, using the signed-in user's own session. */
export async function GET(request: NextRequest): Promise<Response> {
  const start = request.nextUrl.searchParams.get("start") ?? "";
  const end = request.nextUrl.searchParams.get("end") ?? "";
  if (!DATE.test(start) || !DATE.test(end)) {
    return new Response("Choose a start and an end date.", { status: 400 });
  }
  const token = await getAccessToken();
  if (!token) return NextResponse.redirect(new URL("/login", request.url));

  const query = new URLSearchParams({ start, end });
  const upstream = await fetch(
    `${apiBaseUrl()}/analytics/export.csv?${query.toString()}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
  );
  if (upstream.status === 401) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (!upstream.ok) return new Response(null, { status: upstream.status });
  return new Response(await upstream.text(), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="procedures-${start}-${end}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
