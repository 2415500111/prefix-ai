import { Bell, Stethoscope } from "lucide-react";
import Link from "next/link";

import {
  LANGUAGE_LABELS,
  PORTAL_LANGUAGES,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";

import { chooseLanguage } from "../../actions";

/** The glass header: the hospital's name, the language toggle and the Updates bell. */
export function PortalHeader({
  hospital,
  lang,
  unread,
}: {
  hospital: string;
  lang: PortalLang;
  unread: number;
}) {
  const t = PORTAL_TEXT[lang];
  return (
    <header className="sticky top-0 z-40 border-b glass pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex h-16 w-full max-w-xl items-center gap-2 px-4">
        <span
          aria-hidden
          className="hidden size-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground min-[400px]:grid"
        >
          <Stethoscope className="size-5" strokeWidth={1.75} />
        </span>
        <p className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight sm:text-[17px]">
          {hospital}
        </p>
        <LanguageSwitch lang={lang} />
        <Link
          href="/p/updates"
          aria-label={t.bell(unread)}
          className="relative grid size-12 shrink-0 pressable place-items-center rounded-full text-foreground hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
        >
          <Bell aria-hidden className="size-6" strokeWidth={1.75} />
          {unread > 0 ? (
            <span
              aria-hidden
              className="absolute top-1.5 right-1 h-5 min-w-5 rounded-full bg-urgent px-1 text-center text-[12px] leading-5 font-semibold text-white tabular-nums dark:text-[#1a0606]"
            >
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Link>
      </div>
    </header>
  );
}

function LanguageSwitch({ lang }: { lang: PortalLang }) {
  return (
    <form
      action={chooseLanguage}
      aria-label={PORTAL_TEXT[lang].language}
      className="flex shrink-0 rounded-full bg-muted p-0.5"
    >
      {PORTAL_LANGUAGES.map((option) => (
        <button
          key={option}
          type="submit"
          name="lang"
          value={option}
          lang={option}
          aria-pressed={option === lang}
          className="h-11 min-w-11 pressable rounded-full px-2.5 text-[14px] font-medium text-muted-foreground transition-colors focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none aria-pressed:bg-card aria-pressed:text-foreground aria-pressed:shadow-card"
        >
          {LANGUAGE_LABELS[option]}
        </button>
      ))}
    </form>
  );
}
