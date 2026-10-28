import type { ImportReport } from "@prefix/shared";

const NOUN: Record<ImportReport["kind"], [string, string]> = {
  patients: ["patient", "patients"],
  appointments: ["appointment", "appointments"],
};

function records(count: number, kind: ImportReport["kind"]): string {
  const [singular, plural] = NOUN[kind];
  return `${count} ${count === 1 ? singular : plural}`;
}

/** What a check or an import found, row by row. */
export function ImportReportView({ report }: { report: ImportReport }) {
  if (report.committed) {
    return (
      <div role="status" className="rounded-md bg-muted px-3 py-2 text-sm">
        Imported {records(report.imported, report.kind)}.
      </div>
    );
  }

  const clean = report.errors.length === 0 && report.rows > 0;
  return (
    <div className="grid gap-3">
      <p role="status" className="text-sm">
        {clean
          ? `All ${records(report.rows, report.kind)} can be imported. Nothing has been saved yet.`
          : `${report.valid_rows} of ${report.rows} ${
              report.rows === 1 ? "row is" : "rows are"
            } valid. Nothing has been saved. Fix the rows below and check the file again.`}
      </p>
      {report.ignored_columns.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          Not imported because no field matches:{" "}
          {report.ignored_columns.join(", ")}.
        </p>
      ) : null}
      {report.errors.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Line
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Column
                </th>
                <th scope="col" className="py-2 font-medium">
                  Problem
                </th>
              </tr>
            </thead>
            <tbody>
              {report.errors.map((error, index) => (
                <tr key={`${error.line}-${index}`} className="border-t">
                  <td className="py-2 pr-3">{error.line}</td>
                  <td className="py-2 pr-3">{error.column ?? "Whole row"}</td>
                  <td className="py-2">{error.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
