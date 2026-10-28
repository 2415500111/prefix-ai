"use client";

import type { ImportKind } from "@prefix/shared";
import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

import { runImport } from "./actions";
import { canCommit, NO_IMPORT, normalizeNewlines } from "./import-state";
import { ImportReportView } from "./import-report";

const SELECT_CLASS =
  "h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Pick a CSV, check it, then import it. The file is read in the browser and sent as text, so
 * a reset form cannot lose it. The import button appears only for a file that passed its check.
 */
export function ImportForm() {
  const [kind, setKind] = useState<ImportKind>("patients");
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [state, action, pending] = useActionState(runImport, NO_IMPORT);
  const committable = canCommit(state, csv);

  return (
    <form action={action} className="grid gap-6">
      <input type="hidden" name="csv" value={csv} />
      <input type="hidden" name="kind" value={kind} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="import-kind">What the file contains</Label>
          <select
            id="import-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as ImportKind)}
            className={SELECT_CLASS}
          >
            <option value="patients">Patients</option>
            <option value="appointments">Appointments</option>
          </select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="import-file">CSV file</Label>
          <input
            id="import-file"
            type="file"
            accept=".csv,text/csv"
            className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              setFileName(file?.name ?? "");
              setCsv(file ? normalizeNewlines(await file.text()) : "");
            }}
          />
          {fileName ? (
            <p className="text-xs text-muted-foreground">Using {fileName}</p>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          name="intent"
          value="check"
          disabled={csv === "" || pending}
        >
          Check file
        </Button>
        {committable ? (
          <Button type="submit" name="intent" value="import" disabled={pending}>
            Import {state.report?.rows} {kind}
          </Button>
        ) : null}
      </div>

      {state.error ? (
        <p role="alert" className="text-sm text-destructive">
          {state.error}
        </p>
      ) : null}
      {state.report ? <ImportReportView report={state.report} /> : null}
    </form>
  );
}
