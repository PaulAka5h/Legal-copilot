import type { ReactNode } from "react";
import type { ShownDetails } from "@/lib/api/lawyerTypes";
import { format, numberFor, type Dictionary, type Language } from "@/lib/i18n";

/** Filled-in professional details as <dl> rows (rendered inside a .profile-list). Empty fields are skipped. */
export function ProfileDetails({
  details,
  copy,
  language,
}: {
  details: ShownDetails;
  copy: Dictionary["lawyerProfile"];
  language: Language;
}) {
  const rows: [string, ReactNode][] = [];
  const add = (label: string, value: ReactNode | null | undefined) => {
    if (value !== null && value !== undefined && value !== "") rows.push([label, value]);
  };
  add(copy.publicPhone, details.publicPhone);
  add(copy.publicEmail, details.publicEmail);
  add(copy.barEnrollment, details.barEnrollmentNo);
  add(copy.courts, details.courts?.length ? details.courts.join(", ") : null);
  add(copy.practiceAreas, details.practiceAreas?.length
    ? details.practiceAreas.map((area) => copy.practiceAreaOptions[area]).join(", ") : null);
  add(copy.yearsExperience, details.yearsExperience === null || details.yearsExperience === undefined
    ? null : format(copy.yearsValue, { count: numberFor(language, details.yearsExperience) }));
  add(copy.officeAddress, details.officeAddress);
  add(copy.languages, details.languages?.length
    ? details.languages.map((code) => copy.languageOptions[code]).join(", ") : null);
  add(copy.bio, details.bio ? <span className="whitespace-pre-line">{details.bio}</span> : null);

  return (
    <>
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </>
  );
}
