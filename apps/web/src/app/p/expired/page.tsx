import type { Metadata } from "next";

export const metadata: Metadata = { title: "Link expired" };

export default function ExpiredPage() {
  return (
    <main className="flex flex-1 flex-col justify-center gap-4 py-10">
      <h1 className="text-2xl font-semibold">Prefix AI</h1>
      <p>
        Your session has ended or this link is no longer valid. Please ask your
        care team for a new link.
      </p>
      <p lang="hi">
        आपका सत्र समाप्त हो गया है या यह लिंक अब मान्य नहीं है। कृपया अपनी
        देखभाल टीम से नया लिंक माँगें।
      </p>
    </main>
  );
}
