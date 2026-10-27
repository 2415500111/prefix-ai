import type { HealthResponse } from "@prefix/shared";
import { connection } from "next/server";

export async function GET(): Promise<Response> {
  await connection();
  const body: HealthResponse = {
    status: "ok",
    service: "prefix-web",
    version: process.env.npm_package_version ?? "0.0.0",
  };
  return Response.json(body, { headers: { "Cache-Control": "no-store" } });
}
