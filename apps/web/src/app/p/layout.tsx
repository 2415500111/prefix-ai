import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: { default: "My procedure", template: "%s · Prefix AI" },
  // Patient pages must never be indexed or cached by shared caches.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#0f5132",
  width: "device-width",
  initialScale: 1,
};

/** The patient portal: mobile-first, large text, one column. */
export default function PortalLayout({ children }: LayoutProps<"/p">) {
  return (
    <div className="flex flex-1 flex-col bg-muted/40 text-lg leading-relaxed">
      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 py-4 sm:py-8">
        {children}
      </div>
    </div>
  );
}
