import type {
  HearingSummaryVersion,
  SummarySection,
} from "@/lib/api/lawyerTypes";

export const hearingSummaryVersions: Record<string, HearingSummaryVersion[]> =
  {};

export const hearingSummarySections: SummarySection[] = [
  {
    id: "keyNotes",
    claims: [
      {
        id: "key-1",
        type: "document",
        verification: "verified",
        text: {
          en: "The filed papers identify the parties and the relief sought.",
          bn: "দাখিলকৃত কাগজপত্রে পক্ষগণ ও প্রত্যাশিত প্রতিকার চিহ্নিত করা হয়েছে।",
        },
        source: {
          en: "Page 1 of the case file",
          bn: "মামলা ফাইলের পৃষ্ঠা ১",
        },
      },
      {
        id: "key-2",
        type: "lawyer",
        verification: "verified",
        text: {
          en: "The hearing note records the appearance of the parties and the next step.",
          bn: "শুনানির নোটে পক্ষগণের উপস্থিতি ও পরবর্তী ধাপ লিপিবদ্ধ আছে।",
        },
        source: {
          en: "Hearing note",
          bn: "শুনানির নোট",
        },
      },
    ],
  },
  {
    id: "laws",
    claims: [
      {
        id: "law-1",
        type: "document",
        verification: "verified",
        text: {
          en: "The filed papers contain no verified citation to a statutory provision.",
          bn: "দাখিলকৃত কাগজপত্রে কোনো যাচাইকৃত আইনি ধারার উল্লেখ নেই।",
        },
        source: {
          en: "Page 4 of the filed papers",
          bn: "দাখিলকৃত কাগজপত্রের পৃষ্ঠা ৪",
        },
      },
      {
        id: "law-2",
        type: "ai",
        verification: "unverified",
        text: {
          en: "The applicable provision has not been verified; no legal conclusion is drawn.",
          bn: "প্রযোজ্য ধারা যাচাই করা হয়নি; কোনো আইনি সিদ্ধান্তে পৌঁছানো হয়নি।",
        },
        source: {
          en: "No verified legal source in the mock knowledge base",
          bn: "মক জ্ঞানভাণ্ডারে কোনো যাচাইকৃত আইনি উৎস নেই",
        },
      },
    ],
  },
  {
    id: "risks",
    claims: [
      {
        id: "risk-1",
        type: "ai",
        verification: "unverified",
        text: {
          en: "The record does not show whether the opposing party has challenged the filed instrument.",
          bn: "বিরোধী পক্ষ দাখিলকৃত দলিল চ্যালেঞ্জ করেছে কি না, রেকর্ডে তা দেখানো হয় না।",
        },
        source: {
          en: "Page 3 of the filed papers",
          bn: "দাখিলকৃত কাগজপত্রের পৃষ্ঠা ৩",
        },
      },
      {
        id: "risk-2",
        type: "assumption",
        verification: "unverified",
        text: {
          en: "The opposing party may raise an objection to the documents at the next date.",
          bn: "পরবর্তী তারিখে বিরোধী পক্ষ নথিগুলোর বিরুদ্ধে আপত্তি তুলতে পারে।",
        },
        source: {
          en: "No source — working assumption",
          bn: "কোনো উৎস নেই — কর্মগত অনুমান",
        },
      },
    ],
  },
  {
    id: "rights",
    claims: [
      {
        id: "right-1",
        type: "lawyer",
        verification: "verified",
        text: {
          en: "The client's right to be heard was recorded at the hearing.",
          bn: "শুনানিতে মক্কেলের শোনার অধিকার লিপিবদ্ধ হয়েছে।",
        },
        source: {
          en: "Hearing note",
          bn: "শুনানির নোট",
        },
      },
      {
        id: "right-2",
        type: "ai",
        verification: "unverified",
        text: {
          en: "The record does not establish whether any further procedural right was exercised.",
          bn: "আর কোনো কার্যগত অধিকার প্রয়োগ করা হয়েছে কি না, রেকর্ডে তা প্রতিষ্ঠিত হয় না।",
        },
        source: {
          en: "Hearing note",
          bn: "শুনানির নোট",
        },
      },
    ],
  },
  {
    id: "notes",
    claims: [
      {
        id: "note-1",
        type: "document",
        verification: "verified",
        text: {
          en: "The hearing note records the next step directed by the court.",
          bn: "শুনানির নোটে আদালতের নির্দেশিত পরবর্তী ধাপ লিপিবদ্ধ আছে।",
        },
        source: {
          en: "Hearing note",
          bn: "শুনানির নোট",
        },
      },
      {
        id: "note-2",
        type: "assumption",
        verification: "unverified",
        text: {
          en: "The note may be incomplete because it was entered after the hearing.",
          bn: "শুনানি শেষে নোট লেখা হওয়ায় তা অসম্পূর্ণ হতে পারে।",
        },
        source: {
          en: "No source — working assumption",
          bn: "কোনো উৎস নেই — কর্মগত অনুমান",
        },
      },
    ],
  },
  {
    id: "nextSteps",
    claims: [
      {
        id: "next-1",
        type: "lawyer",
        verification: "verified",
        text: {
          en: "Prepare the original documents for the next hearing date.",
          bn: "পরবর্তী শুনানির তারিখের জন্য মূল নথি প্রস্তুত করুন।",
        },
        source: {
          en: "Hearing note",
          bn: "শুনানির নোট",
        },
      },
      {
        id: "next-2",
        type: "ai",
        verification: "unverified",
        text: {
          en: "Confirm the next date from the court record before updating the client.",
          bn: "মক্কেলকে জানানোর আগে আদালতের রেকর্ড থেকে পরবর্তী তারিখ নিশ্চিত করুন।",
        },
        source: {
          en: "No verified court record",
          bn: "কোনো যাচাইকৃত আদালত রেকর্ড নেই",
        },
      },
    ],
  },
];
