import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import { listTaskQueue } from "@/lib/server/dal";

import { completeTask } from "../coordinator/actions";
import { SLA_CLASS, SLA_LABEL } from "../coordinator/sla";

export const metadata: Metadata = { title: "Tasks" };

const TIME = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

async function Queue() {
  const items = await listTaskQueue();
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No open tasks. Well done.</p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">
              Due
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Time left
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Patient
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Task
            </th>
            <th scope="col" className="py-2 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-t">
              <td className="py-2 pr-3">
                {item.due_at ? (
                  <time dateTime={item.due_at}>
                    {TIME.format(new Date(item.due_at))}
                  </time>
                ) : (
                  "No due time"
                )}
              </td>
              <td className="py-2 pr-3">
                <span
                  className={`rounded-full border px-2 py-0.5 ${SLA_CLASS[item.sla]}`}
                >
                  {SLA_LABEL[item.sla]}
                </span>
              </td>
              <td className="py-2 pr-3">
                {item.appointment_id ? (
                  <Link
                    href={`/dashboard?appointment=${item.appointment_id}`}
                    className="underline underline-offset-4"
                  >
                    {item.patient_name}
                  </Link>
                ) : (
                  item.patient_name
                )}
              </td>
              <td className="py-2 pr-3">{item.title}</td>
              <td className="py-2">
                <form
                  action={completeTask.bind(null, item.id, "/dashboard/tasks")}
                >
                  <Button type="submit" variant="outline" size="sm">
                    Log done
                  </Button>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TasksPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Task queue</h1>
        <p className="text-sm text-muted-foreground">
          Work the system opened for you, most overdue first.
        </p>
      </div>
      <Suspense
        fallback={
          <p className="text-sm text-muted-foreground">Loading tasks…</p>
        }
      >
        <Queue />
      </Suspense>
    </main>
  );
}
