import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: { default: "My procedure", template: "%s · Prefix AI" },
  // Patient pages must never be indexed or cached by shared caches.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1118" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

/** The patient portal: mobile-first, 17px text, one column. */
export default function PortalLayout({ children }: LayoutProps<"/p">) {
  return (
    <div className="flex min-h-dvh flex-1 flex-col bg-background text-[17px] leading-[26px]">
      {children}
    </div>
  );
}
