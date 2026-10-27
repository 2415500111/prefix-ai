import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  canApproveProtocols,
  canEditProtocols,
  getCurrentUser,
  getProtocol,
  listProtocolVersions,
} from "@/lib/server/dal";
import { describeCondition, formatOffset } from "@/lib/protocol-form";

import { approveProtocol } from "../actions";
import { ApprovePanel } from "../approve-panel";
import { SampleBadge, StatusBadge } from "../status-badge";

export const metadata: Metadata = { title: "Protocol" };

async function ProtocolDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [protocol, versions, user] = await Promise.all([
    getProtocol(id),
    listProtocolVersions(id),
    getCurrentUser(),
  ]);
  const isDraft = protocol.status === "DRAFT";
  const steps = [...protocol.steps].sort(
    (a, b) =>
      b.offset_minutes - a.offset_minutes || a.sort_order - b.sort_order,
  );

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={protocol.status} />
          {protocol.is_sample ? <SampleBadge /> : null}
          <span className="text-sm text-muted-foreground">
            Version {protocol.version}
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {protocol.name}
        </h1>
        {protocol.description ? (
          <p className="max-w-3xl text-sm text-muted-foreground">
            {protocol.description}
          </p>
        ) : null}
      </div>

      {canEditProtocols(user.role) && protocol.status !== "RETIRED" ? (
        <Link
          href={`/dashboard/protocols/${protocol.id}/edit`}
          className={buttonVariants({
            variant: "outline",
            className: "self-start",
          })}
        >
          {isDraft ? "Edit draft" : "Create new version"}
        </Link>
      ) : null}

      {isDraft && canApproveProtocols(user.role) ? (
        <ApprovePanel
          isSample={protocol.is_sample}
          action={approveProtocol.bind(null, protocol.id)}
        />
      ) : null}

      <section aria-label="Steps" className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Steps (in time order)</h2>
        <ol className="flex flex-col gap-3">
          {steps.map((step) => (
            <li key={step.id} className="rounded-xl border p-4">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">
                  {formatOffset(step.offset_minutes)}
                </span>
                <span>· {step.category.replace("_", " ").toLowerCase()}</span>
                {step.is_critical ? <span>· critical</span> : null}
                {step.requires_confirmation ? (
                  <span>· patient confirms</span>
                ) : null}
                <span>· {describeCondition(step.conditions)}</span>
              </div>
              <p className="mt-1 font-medium">{step.title}</p>
              <p className="mt-1 text-sm">{step.instruction_text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="Versions" className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Versions</h2>
        <ul className="flex flex-col gap-1 text-sm">
          {versions.map((v) => (
            <li key={v.id} className="flex items-center gap-2">
              <Link
                href={`/dashboard/protocols/${v.id}`}
                className="hover:underline"
              >
                Version {v.version}
              </Link>
              <StatusBadge status={v.status} />
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

export default function ProtocolPage({
  params,
}: PageProps<"/dashboard/protocols/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <Link
        href="/dashboard/protocols"
        className="text-sm text-muted-foreground hover:underline"
      >
        ← All protocols
      </Link>
      <Suspense
        fallback={<p className="text-sm text-muted-foreground">Loading…</p>}
      >
        <ProtocolDetail params={params} />
      </Suspense>
    </main>
  );
}
