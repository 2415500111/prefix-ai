"use client";

import type { AssistantReply } from "@prefix/shared";
import { MessageCircleQuestionMark } from "lucide-react";
import { useActionState, useId } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { type PortalLang, PORTAL_TEXT } from "@/lib/portal-i18n";

import { askAssistant, type AssistantState } from "../actions";

const EMERGENCY_OUTCOME = "RED_FLAG";

function ReplyView({
  reply,
  lang,
}: {
  reply: AssistantReply;
  lang: PortalLang;
}) {
  const t = PORTAL_TEXT[lang];
  // Emergency wording is announced at once; other replies politely.
  const emergency = reply.outcome === EMERGENCY_OUTCOME;
  return (
    <div
      role={emergency ? "alert" : "status"}
      className={`flex flex-col gap-3 rounded-2xl p-4 ${
        emergency
          ? "border border-urgent/30 bg-urgent-soft text-urgent-foreground"
          : "bg-muted"
      }`}
    >
      <p className={`text-[15px] ${emergency ? "" : "text-muted-foreground"}`}>
        {reply.question}
      </p>
      <p className="font-medium whitespace-pre-line">{reply.reply}</p>
      {reply.citations.length > 0 ? (
        <div>
          <p className="text-[15px] text-muted-foreground">{t.askSources}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {reply.citations.map((citation) => (
              <li key={citation.event_id}>
                <a
                  className="font-medium text-primary underline underline-offset-4"
                  href={`/p/prep#step-${citation.event_id}`}
                >
                  {citation.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function AssistantPanel({
  appointmentId,
  lang,
  history,
}: {
  appointmentId: string;
  lang: PortalLang;
  history: AssistantReply[];
}) {
  const t = PORTAL_TEXT[lang];
  const [state, action, pending] = useActionState<
    AssistantState | null,
    FormData
  >(askAssistant.bind(null, appointmentId), null);
  const fieldId = useId();
  const latest = state?.reply ?? null;
  // Newest first; the latest answer is shown above, so it is not repeated below.
  const earlier = history.filter((item) => item.id !== latest?.id).reverse();
  const errorText = state?.error ? errorMessage(state.error, t) : null;

  return (
    <section
      aria-labelledby={`ask-${fieldId}`}
      className="flex flex-col gap-4 rounded-[20px] border bg-card p-5 shadow-card"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="grid size-10 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground"
        >
          <MessageCircleQuestionMark className="size-5" strokeWidth={1.75} />
        </span>
        <div>
          <h2 id={`ask-${fieldId}`} className="text-[20px] font-semibold">
            {t.askTitle}
          </h2>
          <p className="text-[15px] text-muted-foreground">{t.askHint}</p>
        </div>
      </div>

      <form action={action} className="flex flex-col gap-3">
        <input type="hidden" name="lang" value={lang} />
        <label htmlFor={`q-${fieldId}`} className="font-medium">
          {t.askLabel}
        </label>
        <Textarea
          id={`q-${fieldId}`}
          name="question"
          maxLength={1000}
          rows={3}
          className="text-[17px]"
        />
        <Button type="submit" className="h-12 text-[17px]" disabled={pending}>
          {pending ? t.askSending : t.askSend}
        </Button>
      </form>

      {errorText ? (
        <p role="alert" className="text-urgent-foreground">
          {errorText}
        </p>
      ) : null}
      {latest ? <ReplyView reply={latest} lang={lang} /> : null}
      <p className="text-[15px] text-muted-foreground">{t.askDisclaimer}</p>

      {earlier.length > 0 ? (
        <details>
          <summary className="flex min-h-12 cursor-pointer items-center font-medium">
            {t.askHistory} ({earlier.length})
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            {earlier.map((item) => (
              <ReplyView key={item.id} reply={item} lang={lang} />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function errorMessage(
  error: NonNullable<AssistantState["error"]>,
  t: (typeof PORTAL_TEXT)["en"],
): string {
  switch (error) {
    case "empty":
      return t.askEmpty;
    case "rateLimited":
      return t.askRateLimited;
    case "failed":
      return t.askFailed;
  }
}
