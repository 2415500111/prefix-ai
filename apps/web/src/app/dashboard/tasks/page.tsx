import type { Metadata } from "next";
import { CircleCheck, Clock } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { ActionButton } from "@/components/action-runner";
import { PageBody, PageHeader } from "@/components/page-header";
import { StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";
import { SkeletonList } from "@/components/ui/skeleton";
import { listTaskQueue } from "@/lib/server/dal";

import { completeTask } from "../coordinator/actions";
import { SLA_LABEL, SLA_TONE } from "../coordinator/sla";

export const metadata: Metadata = { title: "Tasks" };

const TIME = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

async function Queue() {
  // Reschedule requests have their own page (Requests), so they are not repeated here.
  const items = (await listTaskQueue()).filter(
    (item) => item.type !== "RESCHEDULE",
  );
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed bg-card px-6 py-12 text-center">
        <CircleCheck className="mx-auto mb-2 size-8 text-ready" aria-hidden />
        <p className="font-medium">No open tasks. Well done.</p>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Open tasks">
      {items.map((item, index) => (
        <StaggerItem
          key={item.id}
          index={index}
          className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border bg-card px-4 py-3.5 shadow-card"
        >
          <Badge variant={SLA_TONE[item.sla]} className="w-36 justify-start">
            <Clock aria-hidden />
            {SLA_LABEL[item.sla]}
          </Badge>
          <div className="min-w-48 flex-1">
            <p className="font-medium">{item.title}</p>
            <p className="text-sm text-muted-foreground">
              {item.appointment_id ? (
                <Link
                  href={`/dashboard?appointment=${item.appointment_id}`}
                  className="underline-offset-4 hover:underline"
                >
                  {item.patient_name}
                </Link>
              ) : (
                item.patient_name
              )}
              {item.due_at ? (
                <>
                  {" · due "}
                  <time dateTime={item.due_at}>
                    {TIME.format(new Date(item.due_at))}
                  </time>
                </>
              ) : null}
            </p>
          </div>
          <ActionButton
            variant="outline"
            size="sm"
            action={completeTask.bind(null, item.id)}
          >
            <CircleCheck aria-hidden />
            Log done
          </ActionButton>
        </StaggerItem>
      ))}
    </ul>
  );
}

export default function TasksPage() {
  return (
    <PageBody>
      <PageHeader
        title="Task queue"
        description="Work the system opened for you, most overdue first."
      />
      <Suspense fallback={<SkeletonList label="Loading tasks" />}>
        <Queue />
      </Suspense>
    </PageBody>
  );
}
