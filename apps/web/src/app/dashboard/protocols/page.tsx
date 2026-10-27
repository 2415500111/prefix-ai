import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  canEditProtocols,
  getCurrentUser,
  listProcedureTypes,
  listProtocols,
} from "@/lib/server/dal";

import { SampleBadge, StatusBadge } from "./status-badge";

export const metadata: Metadata = { title: "Protocols" };

async function NewProtocolButton() {
  const user = await getCurrentUser();
  if (!canEditProtocols(user.role)) return null;
  return (
    <Link href="/dashboard/protocols/new" className={buttonVariants()}>
      New protocol
    </Link>
  );
}

async function ProtocolTable() {
  const [protocols, procedureTypes] = await Promise.all([
    listProtocols(),
    listProcedureTypes(),
  ]);
  const procedureName = new Map(procedureTypes.map((p) => [p.id, p.name]));

  if (protocols.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No protocols yet. Create one to start building prep timelines.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Protocol</TableHead>
          <TableHead>Procedure</TableHead>
          <TableHead>Version</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {protocols.map((protocol) => (
          <TableRow key={protocol.id}>
            <TableCell className="max-w-md whitespace-normal">
              <Link
                href={`/dashboard/protocols/${protocol.id}`}
                className="font-medium hover:underline"
              >
                {protocol.name}
              </Link>
            </TableCell>
            <TableCell>
              {procedureName.get(protocol.procedure_type_id) ?? "—"}
            </TableCell>
            <TableCell>v{protocol.version}</TableCell>
            <TableCell className="flex gap-1">
              <StatusBadge status={protocol.status} />
              {protocol.is_sample ? <SampleBadge /> : null}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function ProtocolsPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Protocols</h1>
          <p className="text-sm text-muted-foreground">
            Clinician-approved prep instructions. Only approved versions are
            ever sent to patients.
          </p>
        </div>
        <Suspense fallback={null}>
          <NewProtocolButton />
        </Suspense>
      </div>
      <Suspense
        fallback={<p className="text-sm text-muted-foreground">Loading…</p>}
      >
        <ProtocolTable />
      </Suspense>
    </main>
  );
}
