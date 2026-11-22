import Image from "next/image";
import { dictionaries, type Language } from "@/lib/i18n";

export function Logo({ language }: { language: Language }) {
  const copy = dictionaries[language].brand;

  return (
    <span className="logo">
      <Image className="logo-mark" src="/brand/pokkhoai-icon.png" alt="" width={42} height={42} />
      <span className="logo-copy">
        <b>{copy.name}</b>
      </span>
    </span>
  );
}
