import Link from "next/link";
import { Icon } from "@/components/Icon";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export default async function ClientSummaryNotFound() {
  const language = await getLanguage();
  const copy = dictionaries[language].clientSummaries;

  return (
    <div className="panel empty-state">
      <Icon name="document" size={28} />
      <h1>{copy.notAvailable}</h1>
      <p>{copy.notAvailableBody}</p>
      <Link className="ghost-button" href="/client/dashboard">
        {copy.back}
      </Link>
    </div>
  );
}
