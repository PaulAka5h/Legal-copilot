import type {
  ClientCase,
  ClientProfile,
  ClientSummary,
} from "@/lib/api/client";

type StoredSummary = ClientSummary & { status: "approved" | "draft" };

export const clientProfile: ClientProfile = {
  name: { en: "Fahim Rahman", bn: "ফাহিম রহমান" },
};

export const clientCase: Omit<ClientCase, "summaries"> = {
  id: "LC-24018",
  title: { en: "Rahman vs. Karim", bn: "রহমান বনাম করিম" },
  statusLabel: { en: "Active", bn: "সক্রিয়" },
  caseType: { en: "Property dispute", bn: "সম্পত্তি বিরোধ" },
  court: { en: "Dhaka District Court", bn: "ঢাকা জেলা আদালত" },
  hearingNumber: 3,
  stages: [
    {
      id: "filed",
      label: { en: "Case filed", bn: "মামলা দায়ের" },
      note: { en: "12 Sep", bn: "১২ সেপ্টেম্বর" },
      state: "complete",
    },
    {
      id: "notice",
      label: { en: "Notice served", bn: "নোটিশ জারি" },
      note: { en: "28 Sep", bn: "২৮ সেপ্টেম্বর" },
      state: "complete",
    },
    {
      id: "evidence",
      label: { en: "Evidence", bn: "সাক্ষ্য" },
      note: { en: "In progress", bn: "চলমান" },
      state: "current",
    },
    {
      id: "arguments",
      label: { en: "Arguments", bn: "যুক্তিতর্ক" },
      note: { en: "Upcoming", bn: "আসন্ন" },
      state: "upcoming",
    },
    {
      id: "decision",
      label: { en: "Decision", bn: "রায়" },
      note: { en: "Upcoming", bn: "আসন্ন" },
      state: "upcoming",
    },
  ],
  nextHearing: {
    day: 17,
    month: { en: "JAN", bn: "জানু" },
    year: 2025,
    place: {
      en: "Courtroom 4, Dhaka District Court",
      bn: "আদালতকক্ষ ৪, ঢাকা জেলা আদালত",
    },
    dateLabel: {
      en: "Friday at 10:30 AM",
      bn: "শুক্রবার সকাল ১০:৩০",
    },
  },
  lawyer: {
    name: { en: "Farhana Ahmed", bn: "ফারহানা আহমেদ" },
    firm: { en: "Rahman & Associates", bn: "রহমান অ্যান্ড অ্যাসোসিয়েটস" },
    phone: "+880 1711-000000",
    email: "farhana@rahmanlaw.bd",
  },
  documents: [
    {
      id: "doc-petition",
      format: "PDF",
      name: { en: "Petition_Copy.pdf", bn: "আবেদনের কপি" },
      size: { en: "2.4 MB", bn: "২.৪ এমবি" },
      sharedOn: { en: "12 Sep 2024", bn: "১২ সেপ্টেম্বর ২০২৪" },
    },
    {
      id: "doc-order",
      format: "PDF",
      name: { en: "Court_Order_02.pdf", bn: "আদালতের আদেশ ০২" },
      size: { en: "1.1 MB", bn: "১.১ এমবি" },
      sharedOn: { en: "21 Nov 2024", bn: "২১ নভেম্বর ২০২৪" },
    },
    {
      id: "doc-witness",
      format: "PDF",
      name: { en: "Witness_Statement.pdf", bn: "সাক্ষীর বিবৃতি" },
      size: { en: "3.8 MB", bn: "৩.৮ এমবি" },
      sharedOn: { en: "10 Jan 2025", bn: "১০ জানুয়ারি ২০২৫" },
    },
  ],
};

export const storedSummaries: StoredSummary[] = [
  {
    id: "summary-hearing-3",
    title: {
      en: "What happened at hearing 3",
      bn: "শুনানি ৩-এ কী হয়েছে",
    },
    excerpt: {
      en: "The court heard the first witness. The next hearing is on 17 January.",
      bn: "আদালত প্রথম সাক্ষীর বক্তব্য শুনেছেন। পরবর্তী শুনানি ১৭ জানুয়ারি।",
    },
    publishedOn: { en: "15 Jan 2025", bn: "১৫ জানুয়ারি ২০২৫" },
    status: "approved",
  },
  {
    id: "summary-documents",
    title: {
      en: "New documents added",
      bn: "নতুন নথি যোগ হয়েছে",
    },
    excerpt: {
      en: "Your lawyer added the court order and a witness statement to your case.",
      bn: "আপনার আইনজীবী আদালতের আদেশ ও সাক্ষীর বিবৃতি মামলায় যোগ করেছেন।",
    },
    publishedOn: { en: "10 Jan 2025", bn: "১০ জানুয়ারি ২০২৫" },
    status: "approved",
  },
  {
    id: "summary-internal-note",
    title: {
      en: "Internal preparation note",
      bn: "অভ্যন্তরীণ প্রস্তুতি নোট",
    },
    excerpt: {
      en: "Draft note for the legal team. Not approved for the client.",
      bn: "আইনি দলের জন্য খসড়া নোট। মক্কেলের জন্য অনুমোদিত নয়।",
    },
    publishedOn: { en: "16 Jan 2025", bn: "১৬ জানুয়ারি ২০২৫" },
    status: "draft",
  },
];
