import type {
  ClientCase,
  ClientProfile,
  ClientSummary,
  ClientSummarySection,
} from "@/lib/api/client";

type StoredSummary = ClientSummary & {
  status: "approved" | "draft";
  caseId?: string;
  sections?: ClientSummarySection[];
};

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
    id: "summary-h-24018-3",
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
    sections: [
      {
        id: "keyNotes",
        text: {
          en: "The court heard the first witness. The hearing record asks for the original deed next time.",
          bn: "আদালত প্রথম সাক্ষীর বক্তব্য শুনেছেন। পরবর্তী শুনানিতে মূল দলিল আনার কথা রেকর্ডে বলা হয়েছে।",
        },
      },
      {
        id: "laws",
        text: {
          en: "No legal question was decided at this hearing. Your lawyer will explain any legal point when it matters.",
          bn: "এই শুনানিতে কোনো আইনি প্রশ্নের সিদ্ধান্ত হয়নি। কোনো আইনি বিষয় গুরুত্বপূর্ণ হলে আপনার আইনজীবী তা ব্যাখ্যা করবেন।",
        },
      },
      {
        id: "risks",
        text: {
          en: "The other side may question the documents you rely on. Your lawyer is preparing for that.",
          bn: "আপনি যে নথির ওপর নির্ভর করছেন, বিরোধী পক্ষ তা নিয়ে প্রশ্ন তুলতে পারে। আপনার আইনজীবী এর জন্য প্রস্তুতি নিচ্ছেন।",
        },
      },
      {
        id: "rights",
        text: {
          en: "You have the right to be told what happened and to ask your lawyer questions.",
          bn: "কী হয়েছে তা জানার এবং আপনার আইনজীবীকে প্রশ্ন করার অধিকার আপনার আছে।",
        },
      },
      {
        id: "notes",
        text: {
          en: "This is a short update, not the full court record. Your lawyer can explain more.",
          bn: "এটি একটি সংক্ষিপ্ত আপডেট, সম্পূর্ণ আদালতের রেকর্ড নয়। আপনার আইনজীবী আরও ব্যাখ্যা করতে পারেন।",
        },
      },
      {
        id: "nextSteps",
        text: {
          en: "Bring the original deed to your lawyer before the next hearing.",
          bn: "পরবর্তী শুনানির আগে মূল দলিল আপনার আইনজীবীর কাছে আনুন।",
        },
      },
    ],
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
    sections: [
      {
        id: "keyNotes",
        text: {
          en: "Your lawyer added a court order and a witness statement to your case file.",
          bn: "আপনার আইনজীবী মামলার ফাইলে একটি আদালতের আদেশ ও একটি সাক্ষীর বিবৃতি যোগ করেছেন।",
        },
      },
      {
        id: "laws",
        text: {
          en: "These documents are part of the case record. Your lawyer can explain what they mean.",
          bn: "এই নথিগুলো মামলার রেকর্ডের অংশ। এগুলোর অর্থ আপনার আইনজীবী ব্যাখ্যা করতে পারেন।",
        },
      },
      {
        id: "risks",
        text: {
          en: "The other side can read documents shared with the court. Do not put private information in the case file.",
          bn: "আদালতে শেয়ার করা নথি বিরোধী পক্ষ পড়তে পারে। মামলার ফাইলে ব্যক্তিগত তথ্য দেবেন না।",
        },
      },
      {
        id: "rights",
        text: {
          en: "You can ask your lawyer to show you the documents added to your case.",
          bn: "আপনার মামলায় যোগ করা নথি দেখতে আপনার আইনজীবীকে বলতে পারেন।",
        },
      },
      {
        id: "notes",
        text: {
          en: "This update only lists new documents. It does not describe every paper in your case.",
          bn: "এই আপডেটে শুধু নতুন নথির তালিকা আছে। আপনার মামলার সব কাগজ এতে বর্ণনা করা হয়নি।",
        },
      },
      {
        id: "nextSteps",
        text: {
          en: "Read the new documents if you can, and note any questions for your lawyer.",
          bn: "সম্ভব হলে নতুন নথিগুলো পড়ুন এবং আপনার আইনজীবীর জন্য প্রশ্ন লিখে রাখুন।",
        },
      },
    ],
  },
  {
    id: "summary-h-24018-2",
    title: {
      en: "What happened at hearing 2",
      bn: "শুনানি ২-এ কী হয়েছে",
    },
    excerpt: {
      en: "The court framed the issues for trial. Two issues were deferred.",
      bn: "আদালত বিচারের জন্য বিষয়গুলো নির্ধারণ করেছেন। দুটি বিষয় পরবর্তী তারিখে রাখা হয়েছে।",
    },
    publishedOn: { en: "22 Nov 2024", bn: "২২ নভেম্বর ২০২৪" },
    status: "approved",
    sections: [
      {
        id: "keyNotes",
        text: {
          en: "The court listed the issues to decide at trial. Some issues were left for a later date.",
          bn: "আদালত বিচারে সিদ্ধান্তের বিষয়গুলো তালিকাভুক্ত করেছেন। কিছু বিষয় পরবর্তী তারিখের জন্য রাখা হয়েছে।",
        },
      },
      {
        id: "laws",
        text: {
          en: "The issues are based on the claims and documents filed. No legal provision is shared in this update.",
          bn: "বিষয়গুলো দায়ের করা দাবি ও নথির ওপর ভিত্তি করে। এই আপডেটে কোনো আইনি ধারা শেয়ার করা হয়নি।",
        },
      },
      {
        id: "risks",
        text: {
          en: "More issues may be added later, so the case can take longer.",
          bn: "পরে আরও বিষয় যোগ হতে পারে, তাই মামলা দীর্ঘ হতে পারে।",
        },
      },
      {
        id: "rights",
        text: {
          en: "You can ask your lawyer to explain each issue and what it means for you.",
          bn: "প্রতিটি বিষয় এবং এর অর্থ আপনার জন্য কী, তা আপনার আইনজীবীকে জিজ্ঞাসা করতে পারেন।",
        },
      },
      {
        id: "notes",
        text: {
          en: "This update is a summary only. It is not the court's full order.",
          bn: "এই আপডেট শুধু একটি সারসংক্ষেপ। এটি আদালতের সম্পূর্ণ আদেশ নয়।",
        },
      },
      {
        id: "nextSteps",
        text: {
          en: "Ask your lawyer if you need to prepare any document for the next date.",
          bn: "পরবর্তী তারিখের জন্য কোনো নথি প্রস্তুত করতে হবে কি না, আপনার আইনজীবীকে জিজ্ঞাসা করুন।",
        },
      },
    ],
  },
  {
    id: "summary-h-24018-1",
    title: {
      en: "What happened at hearing 1",
      bn: "শুনানি ১-এ কী হয়েছে",
    },
    excerpt: {
      en: "The defendant entered appearance and the next date was fixed.",
      bn: "বিবাদী পক্ষ উপস্থিত হয়েছেন এবং পরবর্তী তারিখ নির্ধারণ করা হয়েছে।",
    },
    publishedOn: { en: "09 Oct 2024", bn: "০৯ অক্টোবর ২০২৪" },
    status: "approved",
    sections: [
      {
        id: "keyNotes",
        text: {
          en: "The defendant came to court. The court fixed the next date for the case.",
          bn: "বিবাদী পক্ষ আদালতে উপস্থিত হয়েছেন। আদালত মামলার পরবর্তী তারিখ নির্ধারণ করেছেন।",
        },
      },
      {
        id: "laws",
        text: {
          en: "No legal question was decided at this hearing.",
          bn: "এই শুনানিতে কোনো আইনি প্রশ্নের সিদ্ধান্ত হয়নি।",
        },
      },
      {
        id: "risks",
        text: {
          en: "The case is still at an early stage, so the result is not known.",
          bn: "মামলা এখনো প্রাথমিক পর্যায়ে, তাই ফলাফল জানা যায়নি।",
        },
      },
      {
        id: "rights",
        text: {
          en: "You will be kept informed about the main steps in your case.",
          bn: "আপনার মামলার প্রধান ধাপগুলো সম্পর্কে আপনাকে জানানো হবে।",
        },
      },
      {
        id: "notes",
        text: {
          en: "This is a short update about the hearing, not legal advice.",
          bn: "এটি শুনানি সম্পর্কে একটি সংক্ষিপ্ত আপডেট, আইনি পরামর্শ নয়।",
        },
      },
      {
        id: "nextSteps",
        text: {
          en: "Contact your lawyer if your address or phone number changes.",
          bn: "আপনার ঠিকানা বা ফোন নম্বর পরিবর্তন হলে আপনার আইনজীবীকে জানান।",
        },
      },
    ],
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
  {
    id: "summary-other-case",
    caseId: "LC-99999",
    title: { en: "Another client's summary", bn: "অন্য মক্কেলের সারসংক্ষেপ" },
    excerpt: {
      en: "This summary belongs to a different client and must not be shown.",
      bn: "এই সারসংক্ষেপটি অন্য মক্কেলের এবং এটি দেখানো যাবে না।",
    },
    publishedOn: { en: "01 Jan 2025", bn: "০১ জানুয়ারি ২০২৫" },
    status: "approved",
  },
];
