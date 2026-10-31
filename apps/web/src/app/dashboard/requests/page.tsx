import type { RescheduleRequest } from "@prefix/shared";
import { cn } from "cn";
import { CalendarClock, Siren } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ActionButton } from "@/components/action-runner";
import { PageBody, PageHeader } from "@/components/page-header";
import { StaggerItem } from "@/components/ui/animated";
import { Badge } from "@/components/ui/badge";
import { FilterChipLink } from "@/components/ui/filter-chip";
import { RaisedTime } from "@/components/ui/raised-time";
import { SkeletonList } from "@/components/ui/skeleton";
import { describeUrgency, URGENT_EDGE, UrgentPill } from "@/components/urgency";
import {
  canAnswerRequests,
  getCurrentUser,
  listRequests,
} from "@/lib/server/dal";

import { approveRequest, declineRequest } from "../coordinator/actions";
import { RescheduleFields } from "../coordinator/reschedule-fields";

export const metadata: Metadata = { title: "Requests" };

function procedureTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

const STATUS = {
  pending: { label: "Waiting for an answer", tone: "attention" },
  approved: { label: "Approved", tone: "ready" },
  declined: { label: "Declined", tone: "neutral" },
} as const;

function RequestCard({
  request,
  index,
  canAnswer,
}: {
  request: RescheduleRequest;
  index: number;
  canAnswer: boolean;
}) {
  const status = STATUS[request.status];
  return (
    <StaggerItem
      index={index}
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl border bg-card px-4 py-3.5 shadow-card",
        request.urgent && URGENT_EDGE,
      )}
    >
      <span
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-full",
          request.urgent
            ? "bg-urgent-soft text-urgent"
            : "bg-primary-soft text-primary-soft-foreground",
        )}
      >
        <CalendarClock className="size-4" aria-hidden />
      </span>
      <div className="min-w-48 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/dashboard?appointment=${request.appointment_id}&tab=requests`}
            className="font-semibold underline-offset-4 hover:underline"
          >
            {request.patient_name}
          </Link>
          {request.urgent ? <UrgentPill /> : null}
        </div>
        <p className="text-sm text-muted-foreground">
          {request.procedure_name} · now{" "}
          <time dateTime={request.scheduled_at}>
            {procedureTime(request.scheduled_at, request.timezone)}
          </time>
        </p>
        <p className="text-sm">
          Asked to move the procedure
          {request.urgent ? (
            <span className="text-urgent-foreground">
              {" "}
              · {describeUrgency(request.urgent_reasons)}
            </span>
          ) : null}
        </p>
        <RaisedTime
          iso={request.created_at}
          timeZone={request.timezone}
          className="block"
        />
      </div>
      <Badge variant={status.tone}>{status.label}</Badge>
      {request.status === "pending" && canAnswer ? (
        <div className="flex gap-2">
          <ActionButton
            size="sm"
            action={approveRequest.bind(null, request.id)}
            confirm={{
              title: `Move ${request.patient_name}'s procedure?`,
              description:
                "The prep plan follows the new time, and the patient sees the answer in their portal.",
              confirmLabel: "Approve and move",
              fields: <RescheduleFields />,
            }}
          >
            Approve
          </ActionButton>
          <ActionButton
            size="sm"
            variant="outline"
            action={declineRequest.bind(null, request.id)}
            confirm={{
              title: "Decline this request?",
              description:
                "The procedure stays at its current time. The patient is asked to call the hospital.",
              confirmLabel: "Decline",
              tone: "danger",
            }}
          >
            Decline
          </ActionButton>
        </div>
      ) : null}
    </StaggerItem>
  );
}

type SearchParams = PageProps<"/dashboard/requests">["searchParams"];

async function Requests({ searchParams }: { searchParams: SearchParams }) {
  const [all, user, params] = await Promise.all([
    listRequests(),
    getCurrentUser(),
    searchParams,
  ]);
  const canAnswer = canAnswerRequests(user.role);
  const urgentOnly = params.urgent === "1";
  const urgentCount = all.filter((request) => request.urgent).length;
  // Newest first, as the API orders them; the sections only split that order.
  const requests = urgentOnly ? all.filter((request) => request.urgent) : all;
  const pending = requests.filter((request) => request.status === "pending");
  const answered = requests.filter((request) => request.status !== "pending");

  return (
    <>
      <div className="flex items-center gap-2">
        <FilterChipLink
          active={urgentOnly}
          href={
            urgentOnly ? "/dashboard/requests" : "/dashboard/requests?urgent=1"
          }
        >
          <Siren className="size-3.5" aria-hidden />
          Urgent only
          <span className="text-xs tabular-nums">{urgentCount}</span>
        </FilterChipLink>
      </div>
      <section
        aria-labelledby="pending-heading"
        className="flex flex-col gap-3"
      >
        <h2
          id="pending-heading"
          className="text-lg font-semibold tracking-tight"
        >
          Waiting for an answer
        </h2>
        {pending.length === 0 ? (
          <p className="rounded-2xl border border-dashed bg-card px-6 py-8 text-center text-sm text-muted-foreground">
            No patient is waiting for an answer.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {pending.map((request, index) => (
              <RequestCard
                key={request.id}
                request={request}
                index={index}
                canAnswer={canAnswer}
              />
            ))}
          </ul>
        )}
      </section>
      {answered.length > 0 ? (
        <section
          aria-labelledby="answered-heading"
          className="flex flex-col gap-3"
        >
          <h2
            id="answered-heading"
            className="text-lg font-semibold tracking-tight"
          >
            Answered this week
          </h2>
          <ul className="flex flex-col gap-2">
            {answered.map((request, index) => (
              <RequestCard
                key={request.id}
                request={request}
                index={index}
                canAnswer={false}
              />
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

export default function RequestsPage({
  searchParams,
}: PageProps<"/dashboard/requests">) {
  return (
    <PageBody>
      <PageHeader
        title="Requests"
        description="Patients who asked to move their procedure, newest first. They see your answer in their portal."
      />
      <Suspense fallback={<SkeletonList label="Loading requests" rows={3} />}>
        <Requests searchParams={searchParams} />
      </Suspense>
    </PageBody>
  );
}
