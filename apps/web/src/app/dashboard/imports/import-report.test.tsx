import type { ImportReport } from "@prefix/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ImportReportView } from "./import-report";

function report(overrides: Partial<ImportReport> = {}): ImportReport {
  return {
    kind: "patients",
    rows: 3,
    valid_rows: 3,
    imported: 0,
    committed: false,
    ignored_columns: [],
    errors: [],
    ...overrides,
  };
}

describe("import report", () => {
  it("says a clean check can be imported and that nothing is saved yet", () => {
    render(<ImportReportView report={report()} />);

    expect(
      screen.getByText(
        "All 3 patients can be imported. Nothing has been saved yet.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("lists each row problem by line, with the column and the rule", () => {
    render(
      <ImportReportView
        report={report({
          valid_rows: 1,
          errors: [
            { line: 3, column: "email", message: "is not valid" },
            {
              line: 4,
              column: null,
              message: "needs patient_mrn or patient_phone",
            },
          ],
        })}
      />,
    );

    expect(
      screen.getByText(
        "1 of 3 rows are valid. Nothing has been saved. Fix the rows below and check the file again.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "email" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Whole row" })).toBeInTheDocument();
    expect(
      screen.getByText("needs patient_mrn or patient_phone"),
    ).toBeInTheDocument();
  });

  it("names the columns that were not imported", () => {
    render(
      <ImportReportView
        report={report({ ignored_columns: ["Clinic Notes"] })}
      />,
    );

    expect(screen.getByText(/Clinic Notes/)).toBeInTheDocument();
  });

  it("confirms how many records were written once an import is committed", () => {
    render(
      <ImportReportView
        report={report({ kind: "appointments", imported: 1, committed: true })}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Imported 1 appointment.",
    );
  });
});
