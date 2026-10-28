"use client";

import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

import { type DemoActionResult, openDemoPatient, resetDemo } from "./actions";

export function DemoControls({ isAdmin }: { isAdmin: boolean }) {
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<DemoActionResult | null>(null);

  function openPatient(lang: "en" | "hi") {
    // Browsers only allow a new tab while the click is still being handled, so the tab is
    // opened now and pointed at the patient's link once the server has answered.
    const tab = window.open("", "_blank");
    startTransition(async () => {
      const outcome = await openDemoPatient(lang);
      if (outcome.ok && outcome.url && tab) {
        tab.opener = null;
        tab.location.href = outcome.url;
        setResult(outcome);
        return;
      }
      tab?.close();
      setResult(
        outcome.ok
          ? {
              ok: false,
              message: "Allow pop-ups for this site to open the demo patient.",
            }
          : outcome,
      );
    });
  }

  function reset() {
    startTransition(async () => {
      setResult(await resetDemo());
    });
  }

  return (
    <section
      aria-labelledby="demo-title"
      className="flex flex-col gap-3 rounded-lg border p-4"
    >
      <div>
        <h2 id="demo-title" className="font-semibold">
          Demo tools
        </h2>
        <p className="text-sm text-muted-foreground">
          See the patient view as a patient would. Demo patients are made up.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          disabled={pending}
          onClick={() => openPatient("en")}
        >
          View patient demo (English)
        </Button>
        <Button
          variant="outline"
          disabled={pending}
          onClick={() => openPatient("hi")}
        >
          View patient demo (Hindi)
        </Button>
        {isAdmin ? (
          <Button variant="secondary" disabled={pending} onClick={reset}>
            Reset demo
          </Button>
        ) : null}
      </div>
      {result ? (
        <p
          role={result.ok ? "status" : "alert"}
          className={`text-sm ${result.ok ? "" : "text-destructive"}`}
        >
          {result.message}
        </p>
      ) : null}
    </section>
  );
}
