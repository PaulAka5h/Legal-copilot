import type { Metadata } from "next";
import { NotConfigured } from "@/components/NotConfigured";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerMatters") };
}

export default async function LawyerMattersPage() {
  const language = await getLanguage();

  return (
    <NotConfigured
      language={language}
      title={dictionaries[language].notConfigured.matters}
    />
  );
}
