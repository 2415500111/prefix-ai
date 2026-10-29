import type { Metadata } from "next";
import { Suspense } from "react";

import { getProtocol, listProcedureTypes } from "@/lib/server/dal";

import { saveProtocol } from "../../actions";
import { ProtocolEditor } from "../../protocol-editor";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Edit protocol" };

async function EditForm({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [protocol, procedureTypes] = await Promise.all([
    getProtocol(id),
    listProcedureTypes(),
  ]);
  return (
    <ProtocolEditor
      protocolId={protocol.id}
      initial={{
        procedure_type_id: protocol.procedure_type_id,
        name: protocol.name,
        description: protocol.description,
        steps: protocol.steps,
      }}
      procedureTypes={procedureTypes}
      createsNewVersion={protocol.status !== "DRAFT"}
      onSave={saveProtocol}
    />
  );
}

export default function EditProtocolPage({
  params,
}: PageProps<"/dashboard/protocols/[id]/edit">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
        Edit protocol
      </h1>
      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <EditForm params={params} />
      </Suspense>
    </main>
  );
}
