import { Phone, Siren } from "lucide-react";

import { PORTAL_TEXT, type PortalLang } from "@/lib/portal-i18n";

const CALL_112 =
  "pressable inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-urgent px-5 text-[17px] font-semibold text-white shadow-card hover:bg-[color-mix(in_oklab,var(--urgent),black_12%)] focus-visible:ring-3 focus-visible:ring-urgent/30 focus-visible:outline-none dark:text-[#1a0606]";

/**
 * Red-flag symptoms always go to emergency services, never to the app (safety rule b), so the
 * emergency notice is on every portal page. Help shows it in full.
 */
export function EmergencyBox({
  lang,
  compact = false,
}: {
  lang: PortalLang;
  compact?: boolean;
}) {
  const t = PORTAL_TEXT[lang];
  return (
    <aside
      aria-labelledby={compact ? "emergency-note" : "emergency-title"}
      className="flex flex-col gap-3 rounded-[20px] border border-urgent/30 bg-urgent-soft p-5 text-urgent-foreground"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="grid size-10 shrink-0 place-items-center rounded-full bg-card text-urgent"
        >
          <Siren className="size-5" strokeWidth={1.75} />
        </span>
        <h2
          id={compact ? "emergency-note" : "emergency-title"}
          className="text-[20px] font-semibold"
        >
          {t.emergencyTitle}
        </h2>
      </div>
      <p className={compact ? "text-[15px] leading-[22px]" : undefined}>
        {t.emergencyText}
      </p>
      <a href="tel:112" className={`${CALL_112} self-start`}>
        <Phone aria-hidden className="size-5" />
        {t.emergencyCall}
      </a>
    </aside>
  );
}
