import { NextResponse, type NextRequest } from "next/server";

import { apiBaseUrl } from "@/lib/server/api";
import { getPatientToken } from "@/lib/server/patient-session";
import { EXPIRED_PATH } from "@/lib/server/portal";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Streams the procedure's .ics file from the API using the patient's httpOnly session. */
export async function GET(
  request: NextRequest,
  ctx: RouteContext<"/p/calendar/[id]">,
): Promise<Response> {
  const { id } = await ctx.params;
  if (!UUID.test(id)) return new Response(null, { status: 404 });
  const token = await getPatientToken();
  if (!token) return NextResponse.redirect(new URL(EXPIRED_PATH, request.url));

  const upstream = await fetch(
    `${apiBaseUrl()}/patient/appointments/${id}/calendar.ics`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
  );
  if (upstream.status === 401) {
    return NextResponse.redirect(new URL(EXPIRED_PATH, request.url));
  }
  if (!upstream.ok) return new Response(null, { status: upstream.status });
  return new Response(await upstream.text(), {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="procedure.ics"',
      "Cache-Control": "no-store",
    },
  });
}
