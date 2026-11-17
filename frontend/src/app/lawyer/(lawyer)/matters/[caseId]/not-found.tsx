import Link from "next/link";
import { Icon } from "@/components/Icon";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export default async function CaseNotFound() {
  const language = await getLanguage();
  const copy = dictionaries[language].caseDetail;

  return (
    <div className="panel empty-state">
      <Icon name="briefcase" size={28} />
      <h1>{copy.notFound}</h1>
      <p>{copy.notFoundBody}</p>
      <Link className="ghost-button" href="/lawyer/matters">
        {copy.back}
      </Link>
    </div>
  );
}
