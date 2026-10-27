import "server-only";

import type { ApiErrorBody } from "@prefix/shared";

import { getAccessToken } from "./session";

/** Server-to-server URL of the FastAPI service (never exposed to the browser). */
export function apiBaseUrl(): string {
  return (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function errorMessage(
  body: ApiErrorBody | null,
  status: number,
): string {
  if (!body) return `Request failed (${status})`;
  if (typeof body.detail === "string") return body.detail;
  return body.detail
    .map((issue) => `${issue.loc.slice(1).join(".")}: ${issue.msg}`)
    .join("; ");
}

interface ApiRequest {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
}

/** Call the API as the signed-in user (or with an explicit token, or anonymously). */
export async function api<T>(
  path: string,
  { method = "GET", body, token }: ApiRequest = {},
): Promise<T> {
  const bearer = token === undefined ? await getAccessToken() : token;
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    const parsed = (await response
      .json()
      .catch(() => null)) as ApiErrorBody | null;
    throw new ApiError(
      response.status,
      errorMessage(parsed, response.status),
      parsed?.code,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
