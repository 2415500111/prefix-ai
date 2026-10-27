"use client";

import { useActionState, useId, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { type ActionResult, confirmStep, reportProblem } from "../actions";

export interface StepActionText {
  confirm: string;
  confirming: string;
  problem: string;
  problemNoteLabel: string;
  sendProblem: string;
  sending: string;
  cancel: string;
  actionFailed: string;
}

const BIG = "h-12 w-full text-base sm:w-auto sm:px-5";

export function StepActions({
  eventId,
  title,
  canConfirm,
  canReportProblem,
  text,
}: {
  eventId: string;
  title: string;
  canConfirm: boolean;
  canReportProblem: boolean;
  text: StepActionText;
}) {
  const [confirming, startConfirm] = useTransition();
  const [confirmFailed, setConfirmFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const [problemState, problemAction, sending] = useActionState<
    ActionResult | null,
    FormData
  >(reportProblem.bind(null, eventId), null);
  const noteId = useId();

  if (!canConfirm && !canReportProblem) return null;
  const failed = confirmFailed || problemState?.ok === false;

  return (
    <div className="mt-3 flex flex-col gap-3">
      {!open ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          {canConfirm ? (
            <Button
              className={BIG}
              disabled={confirming}
              aria-label={`${text.confirm}: ${title}`}
              onClick={() =>
                startConfirm(async () => {
                  const result = await confirmStep(eventId);
                  setConfirmFailed(!result.ok);
                })
              }
            >
              {confirming ? text.confirming : text.confirm}
            </Button>
          ) : null}
          {canReportProblem ? (
            <Button
              variant="outline"
              className={BIG}
              aria-label={`${text.problem}: ${title}`}
              onClick={() => setOpen(true)}
            >
              {text.problem}
            </Button>
          ) : null}
        </div>
      ) : (
        <form action={problemAction} className="flex flex-col gap-2">
          <label htmlFor={noteId} className="text-base font-medium">
            {text.problemNoteLabel}
          </label>
          <Textarea
            id={noteId}
            name="note"
            maxLength={1000}
            rows={3}
            className="text-base"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button type="submit" className={BIG} disabled={sending}>
              {sending ? text.sending : text.sendProblem}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className={BIG}
              onClick={() => setOpen(false)}
            >
              {text.cancel}
            </Button>
          </div>
        </form>
      )}
      {failed ? (
        <p role="alert" className="text-base text-destructive">
          {text.actionFailed}
        </p>
      ) : null}
    </div>
  );
}
