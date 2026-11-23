import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "PokkhoAI",
    short_name: "PokkhoAI",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#076732",
    icons: [{ src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" }],
  };
}
