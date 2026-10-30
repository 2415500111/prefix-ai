import type { Metadata } from "next";
import { Suspense } from "react";

import { listProcedureTypes } from "@/lib/server/dal";

import { saveProtocol } from "../actions";
import { ProtocolEditor } from "../protocol-editor";
import { SkeletonList } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "New protocol" };

async function NewProtocolForm() {
  const procedureTypes = await listProcedureTypes();
  return (
    <ProtocolEditor
      protocolId={null}
      initial={{
        procedure_type_id: "",
        name: "",
        description: null,
        steps: [],
      }}
      procedureTypes={procedureTypes}
      createsNewVersion={false}
      onSave={saveProtocol}
    />
  );
}

export default function NewProtocolPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
        New protocol
      </h1>
      <Suspense fallback={<SkeletonList label="Loading" rows={3} />}>
        <NewProtocolForm />
      </Suspense>
    </main>
  );
}
