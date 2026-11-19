import type { Metadata } from "next";
import type { ReactNode } from "react";
import {
  Cormorant_Garamond,
  Hind_Siliguri,
  Inter,
  Noto_Serif_Bengali,
} from "next/font/google";
import { getLanguage } from "@/lib/language";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-cormorant",
  display: "swap",
});

const hind = Hind_Siliguri({
  subsets: ["bengali", "latin"],
  weight: ["400", "500", "600"],
  variable: "--font-hind",
  display: "swap",
});

const notoSerifBengali = Noto_Serif_Bengali({
  subsets: ["bengali"],
  weight: ["600", "700"],
  variable: "--font-noto-serif-bengali",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PokkhoAI",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const language = await getLanguage();

  return (
    <html
      lang={language}
      className={`${inter.variable} ${cormorant.variable} ${hind.variable} ${notoSerifBengali.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
