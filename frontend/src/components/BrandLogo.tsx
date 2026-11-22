import Image from "next/image";

/** Full stacked PokkhoAI logo (icon + wordmark) for login, signup and landing. */
export function BrandLogo({ light = false, priority = false }: { light?: boolean; priority?: boolean }) {
  return (
    <Image
      className={`brand-logo ${light ? "brand-logo-light" : ""}`}
      src="/brand/pokkhoai-logo-full.png"
      alt="PokkhoAI"
      width={555}
      height={462}
      sizes="(max-width: 900px) 84px, 180px"
      priority={priority}
    />
  );
}
