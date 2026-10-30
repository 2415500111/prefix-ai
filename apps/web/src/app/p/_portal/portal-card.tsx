import { Stethoscope } from "lucide-react";
import type { ReactNode } from "react";

/** A calm centred card for the pages a patient sees before they are signed in. */
export function PortalCard({ children }: { children: ReactNode }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-10">
      <div className="flex w-full max-w-md flex-col gap-4 rounded-[20px] border bg-card p-6 shadow-card">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="grid size-11 place-items-center rounded-2xl bg-primary text-primary-foreground"
          >
            <Stethoscope className="size-6" strokeWidth={1.75} />
          </span>
          <h1 className="text-xl font-semibold tracking-tight">Prefix AI</h1>
        </div>
        {children}
      </div>
    </main>
  );
}
