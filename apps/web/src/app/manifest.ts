import type { MetadataRoute } from "next";

/** Lets patients add their prep plan to the home screen like an app. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Prefix AI – My procedure prep",
    short_name: "My prep",
    description: "Your personal plan to get ready for your procedure.",
    start_url: "/p/home",
    scope: "/p",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0f5132",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
