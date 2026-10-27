"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { redeemMagicLink } from "./actions";

type Status = "working" | "missing" | "invalid" | "error";

/** Both languages: we do not know the patient's language until they are signed in. */
const MESSAGES: Record<Status, { en: string; hi: string }> = {
  working: {
    en: "Opening your prep plan…",
    hi: "आपकी तैयारी की योजना खोली जा रही है…",
  },
  missing: {
    en: "Please open the link from the message your hospital sent you.",
    hi: "कृपया अस्पताल के भेजे गए संदेश वाला लिंक खोलें।",
  },
  invalid: {
    en: "This link has expired or was already used. Please ask your care team for a new link.",
    hi: "यह लिंक पुराना हो गया है या पहले ही इस्तेमाल हो चुका है। कृपया अपनी देखभाल टीम से नया लिंक माँगें।",
  },
  error: {
    en: "Something went wrong. Please try again in a few minutes.",
    hi: "कुछ गड़बड़ हो गई। कृपया कुछ मिनट बाद फिर से कोशिश करें।",
  },
};

export function readToken(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, "")).get("token");
}

export function RedeemLink() {
  const [status, setStatus] = useState<Status>("working");
  const [, startTransition] = useTransition();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = readToken(window.location.hash);
    // Remove the single-use token from the address bar and browser history at once.
    window.history.replaceState(null, "", window.location.pathname);
    startTransition(async () => {
      if (!token) {
        setStatus("missing");
        return;
      }
      try {
        const result = await redeemMagicLink(token);
        if (!result.ok) setStatus("invalid");
      } catch {
        setStatus("error");
      }
    });
  }, []);

  const message = MESSAGES[status];
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <p>{message.en}</p>
      <p lang="hi">{message.hi}</p>
    </div>
  );
}
