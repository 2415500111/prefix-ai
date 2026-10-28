"use server";

import type { ImportKind, ImportReport } from "@prefix/shared";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

import { type ImportState, normalizeNewlines } from "./import-state";

const MAX_CHARS = 1_000_000;
const KINDS: readonly string[] = [
  "patients",
  "appointments",
] satisfies ImportKind[];

/**
 * Checks the file (a dry run), or imports it when the button named "import" was pressed.
 * The API decides whether anything is written; this only checks the shape of the request.
 */
export async function runImport(
  _previous: ImportState,
  formData: FormData,
): Promise<ImportState> {
  const kind = String(formData.get("kind") ?? "");
  const csv = String(formData.get("csv") ?? "");
  if (!KINDS.includes(kind)) {
    return { error: "Choose what the file contains." };
  }
  if (csv.trim() === "") {
    return { error: "Choose a CSV file first." };
  }
  if (csv.length > MAX_CHARS) {
    return { error: "The file is larger than 1 MB." };
  }
  const dryRun = formData.get("intent") !== "import";
  try {
    const report = await api<ImportReport>(`/imports/${kind}`, {
      method: "POST",
      body: { csv, dry_run: dryRun },
    });
    return { report, checkedCsv: normalizeNewlines(csv) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    if (error instanceof ApiError) return { error: error.message };
    throw error;
  }
}
