"use client";

import { CircleCheck } from "lucide-react";
import { type FormEvent, useId, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { PORTAL_TEXT, type PortalLang } from "@/lib/portal-i18n";

import { confirmStep, reportProblem } from "../actions";

const BIG = "h-12 w-full text-[17px]";

/** "Yes, done" and "I have a problem" for one step. The problem opens a bottom sheet. */
export function StepActions({
  eventId,
  title,
  canConfirm,
  canReportProblem,
  lang,
}: {
  eventId: string;
  title: string;
  canConfirm: boolean;
  canReportProblem: boolean;
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  const [confirming, startConfirm] = useTransition();
  const [sending, startSend] = useTransition();
  const [open, setOpen] = useState(false);
  const noteId = useId();

  if (!canConfirm && !canReportProblem) return null;

  function confirm(): void {
    startConfirm(async () => {
      const result = await confirmStep(eventId);
      if (result.ok) toast.success(t.confirmedToast, { description: title });
      else toast.error(t.actionFailed);
    });
  }

  function sendProblem(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    startSend(async () => {
      const result = await reportProblem(eventId, null, form);
      if (result.ok) {
        setOpen(false);
        toast.success(t.problemSentToast, { description: title });
      } else {
        toast.error(t.actionFailed);
      }
    });
  }

  return (
    <div className="mt-4 grid gap-2 sm:grid-cols-2">
      {canConfirm ? (
        <Button
          className={BIG}
          disabled={confirming}
          aria-label={`${t.confirm}: ${title}`}
          onClick={confirm}
        >
          <CircleCheck aria-hidden className="size-5" />
          {confirming ? t.confirming : t.confirm}
        </Button>
      ) : null}
      {canReportProblem ? (
        <Sheet
          open={open}
          onOpenChange={setOpen}
          side="bottom"
          className="sm:inset-x-[max(1rem,calc(50%-18rem))]"
          title={t.problemSheetTitle}
          description={t.problemSheetHint(title)}
          closeLabel={t.close}
          trigger={
            <Button
              variant="outline"
              className={BIG}
              aria-label={`${t.problem}: ${title}`}
            >
              {t.problem}
            </Button>
          }
        >
          <form
            onSubmit={sendProblem}
            lang={lang}
            className="flex flex-col gap-3 p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)]"
          >
            <label htmlFor={noteId} className="font-medium">
              {t.problemNoteLabel}
            </label>
            <Textarea
              id={noteId}
              name="note"
              maxLength={1000}
              rows={4}
              className="text-[17px]"
            />
            <Button type="submit" className={BIG} disabled={sending}>
              {sending ? t.sending : t.sendProblem}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className={BIG}
              onClick={() => setOpen(false)}
            >
              {t.cancel}
            </Button>
          </form>
        </Sheet>
      ) : null}
    </div>
  );
}
