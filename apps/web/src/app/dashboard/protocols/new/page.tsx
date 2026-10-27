import type { Metadata } from "next";
import { Suspense } from "react";

import { listProcedureTypes } from "@/lib/server/dal";

import { saveProtocol } from "../actions";
import { ProtocolEditor } from "../protocol-editor";

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
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">New protocol</h1>
      <Suspense
        fallback={<p className="text-sm text-muted-foreground">Loading…</p>}
      >
        <NewProtocolForm />
      </Suspense>
    </main>
  );
}
