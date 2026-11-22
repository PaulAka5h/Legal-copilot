import type { Metadata } from "next";
import type { ReactNode } from "react";
import { getLanguage } from "@/lib/language";
import "./globals.css";

const description =
  "AI legal decision support for Bangladesh lawyers: facts, research and strategy, always reviewed by the lawyer.";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.APP_ORIGIN || "http://localhost:3000"),
  title: {
    template: "%s · PokkhoAI",
    default: "PokkhoAI",
  },
  description,
  applicationName: "PokkhoAI",
  icons: {
    icon: [
      { url: "/brand/favicon.ico", sizes: "any" },
      { url: "/brand/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/brand/icon-16.png", sizes: "16x16", type: "image/png" },
    ],
    shortcut: "/brand/favicon.ico",
    apple: { url: "/brand/apple-icon.png", sizes: "180x180", type: "image/png" },
  },
  openGraph: {
    type: "website",
    siteName: "PokkhoAI",
    title: "PokkhoAI",
    description,
    images: [{ url: "/brand/og-image.png", width: 1200, height: 630, alt: "PokkhoAI" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "PokkhoAI",
    description,
    images: ["/brand/og-image.png"],
  },
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const language = await getLanguage();

  return (
    <html lang={language}>
      <body>{children}</body>
    </html>
  );
}
