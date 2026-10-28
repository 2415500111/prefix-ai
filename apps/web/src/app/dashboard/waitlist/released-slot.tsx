import type { ReleasedSlot } from "@prefix/shared";

import { Button } from "@/components/ui/button";

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
    <article className="rounded-lg border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium">{slot.procedure_name}</h3>
        <time
          dateTime={slot.scheduled_at}
          className="text-sm text-muted-foreground"
        >
          {TIME.format(new Date(slot.scheduled_at))}
        </time>
      </div>
      <p className="text-sm text-muted-foreground">{slot.facility_name}</p>

      {offer ? (
        <div className="mt-3 rounded-md bg-muted p-3 text-sm">
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
              <form action={acceptOffer.bind(null, offer.id)}>
                <Button type="submit" size="sm">
                  Accept
                </Button>
              </form>
              <form action={declineOffer.bind(null, offer.id)}>
                <Button type="submit" variant="outline" size="sm">
                  Decline
                </Button>
              </form>
            </div>
          ) : null}
        </div>
      ) : canManage ? (
        <form
          className="mt-3"
          action={findBackfill.bind(null, slot.appointment_id)}
        >
          <Button type="submit" variant="outline" size="sm">
            Find backfill
          </Button>
        </form>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">No offer made yet.</p>
      )}
    </article>
  );
}
