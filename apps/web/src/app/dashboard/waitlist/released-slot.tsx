import type { ReleasedSlot } from "@prefix/shared";
import { CalendarX, Sparkles } from "lucide-react";

import { ActionButton } from "@/components/action-runner";

import { acceptOffer, declineOffer, findBackfill } from "./actions";

const TIME = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

/** One cancelled slot: the offer it has, or the button that makes one. */
export function ReleasedSlotCard({
  slot,
  canManage,
}: {
  slot: ReleasedSlot;
  canManage: boolean;
}) {
  const offer = slot.open_offer;
  return (
    <article className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-card">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-attention-soft text-attention-foreground">
          <CalendarX className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">{slot.procedure_name}</h3>
          <p className="text-sm text-muted-foreground">
            <time dateTime={slot.scheduled_at}>
              {TIME.format(new Date(slot.scheduled_at))}
            </time>
            {" · "}
            {slot.facility_name}
          </p>
        </div>
      </div>

      {offer ? (
        <div className="rounded-xl bg-primary-soft/50 p-4 text-sm">
          <p>
            Offered to <strong>{offer.patient_name}</strong>. Waiting for a
            reply.
          </p>
          <ul className="mt-2 list-disc pl-5 text-muted-foreground">
            {offer.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          {canManage ? (
            <div className="mt-3 flex gap-2">
              <ActionButton
                size="sm"
                action={acceptOffer.bind(null, offer.id)}
                confirm={{
                  title: `Book ${offer.patient_name} into this slot?`,
                  description:
                    "Their prep plan starts now, built from the approved protocol.",
                  confirmLabel: "Book",
                }}
              >
                Accept
              </ActionButton>
              <ActionButton
                size="sm"
                variant="outline"
                action={declineOffer.bind(null, offer.id)}
              >
                Decline
              </ActionButton>
            </div>
          ) : null}
        </div>
      ) : canManage ? (
        <div>
          <ActionButton
            variant="soft"
            size="sm"
            action={findBackfill.bind(null, slot.appointment_id)}
          >
            <Sparkles aria-hidden />
            Find backfill
          </ActionButton>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No offer made yet.</p>
      )}
    </article>
  );
}
