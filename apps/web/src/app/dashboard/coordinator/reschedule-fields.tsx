import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** The new-time field used when rescheduling or approving a reschedule request. */
export function RescheduleFields() {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="new-time">New date and time (India time)</Label>
      <Input id="new-time" name="scheduled_at" type="datetime-local" required />
    </div>
  );
}
