"use client";

import { useActionState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import type { ActionResult } from "./actions";

export function ApprovePanel({
  isSample,
  action,
}: {
  isSample: boolean;
  action: (state: ActionResult, formData: FormData) => Promise<ActionResult>;
}) {
  const [state, formAction, pending] = useActionState(action, { error: null });

  return (
    <form
      action={formAction}
      className="flex flex-col gap-3 rounded-xl border p-4"
    >
      <h2 className="font-semibold">Approve this version</h2>
      <p className="text-sm text-muted-foreground">
        Once approved, this version is locked and becomes the one used for new
        patient timelines. Any later change creates a new draft.
      </p>
      {isSample ? (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            name="acknowledge_sample"
            required
            className="mt-1"
          />
          <span>
            This is a <strong>SAMPLE</strong> protocol. I confirm our clinical
            team has reviewed every step, time and condition and adapted it to
            our local guidance.
          </span>
        </label>
      ) : null}
      {state.error ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      ) : null}
      <Button type="submit" disabled={pending} className="self-start">
        {pending ? "Approving…" : "Approve"}
      </Button>
    </form>
  );
}
