import type { ImportReport } from "@prefix/shared";

/** What the import form shows after an action: the last check or import, or an error. */
export interface ImportState {
  report?: ImportReport;
  /** The CSV text that `report` describes, so a changed file cannot be imported unchecked. */
  checkedCsv?: string;
  error?: string;
}

export const NO_IMPORT: ImportState = {};

/**
 * Browsers send form text with CRLF line endings, while a file read in the page has LF. Both
 * sides use this so that the same file always compares equal.
 */
export function normalizeNewlines(text: string): string {
  return text.replace(/\r\n?/g, "\n");
}

/** A file may be imported only when its last check had no errors and it has not changed since. */
export function canCommit(state: ImportState, csv: string): boolean {
  const report = state.report;
  return (
    report !== undefined &&
    !report.committed &&
    report.rows > 0 &&
    report.errors.length === 0 &&
    state.checkedCsv === csv
  );
}
