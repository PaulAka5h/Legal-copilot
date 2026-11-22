import { initials } from "@/lib/initials";

/** Photo from an authorized API URL, or initials when there is none. */
export function Avatar({ name, src, size = 35 }: { name: string; src: string | null; size?: number }) {
  if (!src) {
    return (
      <span className="avatar" style={{ width: size, height: size }}>
        {initials(name)}
      </span>
    );
  }
  // A plain <img>: the photo comes from a cookie-authorized API route, which next/image's optimizer cannot fetch.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="avatar avatar-photo" src={src} alt="" width={size} height={size} />;
}

export function lawyerPhotoUrl(photoId: string | null, size: 96 | 512 = 96): string | null {
  return photoId ? `/api/v1/lawyer/profile/photo?size=${size}&v=${encodeURIComponent(photoId)}` : null;
}

export function clientLawyerPhotoUrl(caseId: string, photoId: string | null, size: 96 | 512 = 96): string | null {
  return photoId
    ? `/api/v1/client/cases/${encodeURIComponent(caseId)}/lawyer/photo?size=${size}&v=${encodeURIComponent(photoId)}`
    : null;
}
