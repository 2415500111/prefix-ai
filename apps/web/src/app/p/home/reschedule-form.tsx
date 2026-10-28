"use client";

import { useActionState, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { type ActionResult, requestReschedule } from "../actions";

export interface RescheduleText {
  reschedule: string;
  rescheduleNoteLabel: string;
  rescheduleSend: string;
  sending: string;
  cancel: string;
  actionFailed: string;
}

export function RescheduleForm({
  appointmentId,
  text,
}: {
  appointmentId: string;
  text: RescheduleText;
}) {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState<
    ActionResult | null,
    FormData
  >(requestReschedule.bind(null, appointmentId), null);
  const noteId = useId();

  if (!open) {
    return (
      <Button
        variant="outline"
        className="h-12 w-full text-base"
        onClick={() => setOpen(true)}
      >
        {text.reschedule}
      </Button>
    );
  }
  return (
    <form action={action} className="flex flex-col gap-2">
      <label htmlFor={noteId} className="text-base font-medium">
        {text.rescheduleNoteLabel}
      </label>
      <Textarea
        id={noteId}
        name="note"
        maxLength={1000}
        rows={3}
        className="text-base"
      />
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="submit" className="h-12 text-base" disabled={pending}>
          {pending ? text.sending : text.rescheduleSend}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="h-12 text-base"
          onClick={() => setOpen(false)}
        >
          {text.cancel}
        </Button>
      </div>
      {state?.ok === false ? (
        <p role="alert" className="text-base text-destructive">
          {text.actionFailed}
        </p>
      ) : null}
    </form>
  );
}
