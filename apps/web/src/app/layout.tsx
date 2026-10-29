import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Devanagari } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

// Apple devices use SF Pro from the system stack; Inter is the fallback everywhere else.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

// Hindi gets a Devanagari face with matching weight and height.
const devanagari = Noto_Sans_Devanagari({
  variable: "--font-devanagari",
  subsets: ["devanagari"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Prefix AI",
    template: "%s · Prefix AI",
  },
  description:
    "Prefix AI prevents last-minute cancellations of surgeries, colonoscopies, and imaging scans caused by improper patient preparation.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1118" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${devanagari.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
