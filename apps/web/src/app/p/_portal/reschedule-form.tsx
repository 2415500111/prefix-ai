"use client";

import { CalendarSync } from "lucide-react";
import { type FormEvent, useId, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { PORTAL_TEXT, type PortalLang } from "@/lib/portal-i18n";

import { requestReschedule } from "../actions";

const BIG = "h-12 w-full text-[17px]";

/** Ask the care team to move a procedure, with an optional note, from a bottom sheet. */
export function RescheduleForm({
  appointmentId,
  procedureName,
  lang,
}: {
  appointmentId: string;
  procedureName: string;
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const noteId = useId();

  function send(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    startTransition(async () => {
      const result = await requestReschedule(appointmentId, null, form);
      if (result.ok) {
        setOpen(false);
        toast.success(t.rescheduleSentToast, {
          description: t.rescheduleRequested,
        });
      } else {
        toast.error(t.actionFailed);
      }
    });
  }

  return (
    <Sheet
      open={open}
      onOpenChange={setOpen}
      side="bottom"
      className="sm:inset-x-[max(1rem,calc(50%-18rem))]"
      title={t.rescheduleTitle}
      description={procedureName}
      closeLabel={t.close}
      trigger={
        <Button variant="outline" className={BIG}>
          <CalendarSync aria-hidden className="size-5" />
          {t.reschedule}
        </Button>
      }
    >
      <form
        onSubmit={send}
        lang={lang}
        className="flex flex-col gap-3 p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)]"
      >
        <p className="text-muted-foreground">{t.rescheduleHint}</p>
        <label htmlFor={noteId} className="font-medium">
          {t.rescheduleNoteLabel}
        </label>
        <Textarea
          id={noteId}
          name="note"
          maxLength={1000}
          rows={4}
          className="text-[17px]"
        />
        <Button type="submit" className={BIG} disabled={pending}>
          {pending ? t.sending : t.rescheduleSend}
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
  );
}
