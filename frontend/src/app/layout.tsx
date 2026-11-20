import type { Metadata } from "next";
import type { ReactNode } from "react";
import { getLanguage } from "@/lib/language";
import "./globals.css";

export const metadata: Metadata = {
  title: "PokkhoAI",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const language = await getLanguage();

  return (
    <html lang={language}>
      <body>{children}</body>
    </html>
  );
}
