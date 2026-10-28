import type { ImportReport } from "@prefix/shared";
import { describe, expect, it } from "vitest";

import {
  canCommit,
  type ImportState,
  NO_IMPORT,
  normalizeNewlines,
} from "./import-state";

function report(overrides: Partial<ImportReport> = {}): ImportReport {
  return {
    kind: "patients",
    rows: 2,
    valid_rows: 2,
    imported: 0,
    committed: false,
    ignored_columns: [],
    errors: [],
    ...overrides,
  };
}

const CSV = "first_name,last_name,date_of_birth\nAsha,Patel,1968-03-14";

describe("canCommit", () => {
  it("allows an import of a file that passed its check, unchanged", () => {
    const state: ImportState = { report: report(), checkedCsv: CSV };

    expect(canCommit(state, CSV)).toBe(true);
  });

  it("refuses a file that was edited after its check", () => {
    const state: ImportState = { report: report(), checkedCsv: CSV };

    expect(canCommit(state, `${CSV}\nRavi,Kumar,1971-07-02`)).toBe(false);
  });

  it("refuses a file with any row error", () => {
    const state: ImportState = {
      report: report({
        valid_rows: 1,
        errors: [{ line: 3, column: "email", message: "is not valid" }],
      }),
      checkedCsv: CSV,
    };

    expect(canCommit(state, CSV)).toBe(false);
  });

  it("refuses a second import of the same file once it is committed", () => {
    const state: ImportState = {
      report: report({ committed: true, imported: 2 }),
      checkedCsv: CSV,
    };

    expect(canCommit(state, CSV)).toBe(false);
  });

  it("refuses when nothing has been checked yet", () => {
    expect(canCommit(NO_IMPORT, CSV)).toBe(false);
  });

  it("matches the same file whatever line endings the form sent it with", () => {
    // Browsers send form text with CRLF line endings; the page reads the file with LF.
    const checked = normalizeNewlines(CSV.replace(/\n/g, "\r\n"));
    const state: ImportState = { report: report(), checkedCsv: checked };

    expect(canCommit(state, normalizeNewlines(CSV))).toBe(true);
  });
});

describe("normalizeNewlines", () => {
  it("turns CRLF and lone CR into LF", () => {
    expect(normalizeNewlines("a\r\nb\rc\nd")).toBe("a\nb\nc\nd");
  });
});
