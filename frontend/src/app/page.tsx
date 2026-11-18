import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthLayout } from "@/components/AuthLayout";
import { Icon } from "@/components/Icon";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { getSession } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "home") };
}

export default async function Home() {
  const session = await getSession();
  if (session) {
    redirect(
      session.role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard",
    );
  }

  const language = await getLanguage();
  const entry = dictionaries[language].entry;

  return (
    <AuthLayout type="lawyer" language={language}>
      <span className="eyebrow">{entry.eyebrow}</span>
      <h2>{entry.title}</h2>
      <p className="form-intro">{entry.intro}</p>
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Link className="primary-button" href="/lawyer/login">
            {entry.lawyer}
            <Icon name="arrow" size={19} />
          </Link>
          <p className="m-0 pl-1 text-[11px] text-[#6c757d]">
            {entry.newLawyer}{" "}
            <Link className="font-bold text-[#076732]" href="/lawyer/signup">
              {entry.createAccount}
            </Link>
          </p>
        </div>
        <Link className="primary-button" href="/client/login">
          {entry.client}
          <Icon name="arrow" size={19} />
        </Link>
      </div>
    </AuthLayout>
  );
}
