import type {
  Activity,
  CaseDocument,
  Client,
  Hearing,
  LawyerProfile,
  Localized,
  Matter,
  MatterStage,
} from "@/lib/api/lawyerTypes";

export const matterStages: MatterStage[] = [
  { id: "filed", label: { en: "Case filed", bn: "মামলা দায়ের" } },
  { id: "notice", label: { en: "Notice served", bn: "নোটিশ জারি" } },
  { id: "evidence", label: { en: "Evidence", bn: "সাক্ষ্য" } },
  { id: "arguments", label: { en: "Arguments", bn: "যুক্তিতর্ক" } },
  { id: "decision", label: { en: "Decision", bn: "রায়" } },
];

export const lawyerProfile: LawyerProfile = {
  firstName: { en: "Farhana", bn: "ফারহানা" },
  name: { en: "Farhana Ahmed", bn: "ফারহানা আহমেদ" },
  email: "farhana@rahmanlaw.bd",
  firm: { en: "Rahman & Associates", bn: "রহমান অ্যান্ড অ্যাসোসিয়েটস" },
  location: { en: "Dhaka, Bangladesh", bn: "ঢাকা, বাংলাদেশ" },
};

export const matters: Matter[] = [
  {
    id: "LC-24018",
    title: { en: "Rahman vs. Karim", bn: "রহমান বনাম করিম" },
    clientId: "CL-7842-BD",
    clientName: { en: "Fahim Rahman", bn: "ফাহিম রহমান" },
    court: { en: "Dhaka District Court", bn: "ঢাকা জেলা আদালত" },
    caseType: { en: "Property dispute", bn: "সম্পত্তি বিরোধ" },
    hearingNumber: 3,
    status: "active",
    nextHearing: {
      day: 17,
      month: { en: "JAN", bn: "জানু" },
      time: { en: "10:30 AM", bn: "সকাল ১০:৩০" },
    },
    stages: [
      { ...matterStages[0], date: { en: "12 Sep", bn: "১২ সেপ্টেম্বর" } },
      { ...matterStages[1], date: { en: "28 Sep", bn: "২৮ সেপ্টেম্বর" } },
      matterStages[2],
      matterStages[3],
      matterStages[4],
    ],
    currentStageId: "evidence",
  },
  {
    id: "LC-24012",
    title: { en: "Ahmed Property Matter", bn: "আহমেদ সম্পত্তি বিষয়ক" },
    clientId: "CL-7851-BD",
    clientName: { en: "Nusrat Ahmed", bn: "নুসরাত আহমেদ" },
    court: { en: "High Court Division", bn: "হাইকোর্ট বিভাগ" },
    caseType: { en: "Property dispute", bn: "সম্পত্তি বিরোধ" },
    hearingNumber: 2,
    status: "active",
    nextHearing: {
      day: 19,
      month: { en: "JAN", bn: "জানু" },
      time: { en: "12:00 PM", bn: "দুপুর ১২:০০" },
    },
    stages: [
      { ...matterStages[0], date: { en: "02 Dec", bn: "২ ডিসেম্বর" } },
      { ...matterStages[1], date: { en: "20 Dec", bn: "২০ ডিসেম্বর" } },
      matterStages[2],
      matterStages[3],
      matterStages[4],
    ],
    currentStageId: "evidence",
  },
  {
    id: "LC-23997",
    title: { en: "Khan & Co. Agreement", bn: "খান অ্যান্ড কোং চুক্তি" },
    clientId: "CL-7863-BD",
    clientName: { en: "Rafiq Khan", bn: "রফিক খান" },
    court: { en: "Arbitration Tribunal", bn: "সালিশি ট্রাইব্যুনাল" },
    caseType: { en: "Contract", bn: "চুক্তি" },
    hearingNumber: 5,
    status: "active",
    nextHearing: {
      day: 21,
      month: { en: "JAN", bn: "জানু" },
      time: { en: "11:15 AM", bn: "সকাল ১১:১৫" },
    },
    stages: [
      { ...matterStages[0], date: { en: "10 Aug", bn: "১০ আগস্ট" } },
      { ...matterStages[1], date: { en: "22 Aug", bn: "২২ আগস্ট" } },
      { ...matterStages[2], date: { en: "15 Oct", bn: "১৫ অক্টোবর" } },
      matterStages[3],
      matterStages[4],
    ],
    currentStageId: "arguments",
  },
  {
    id: "LC-23986",
    title: { en: "Sultana Family Matter", bn: "সুলতানা পারিবারিক বিষয়" },
    clientId: "CL-7870-BD",
    clientName: { en: "Samira Sultana", bn: "সামিরা সুলতানা" },
    court: { en: "Family Court, Dhaka", bn: "পারিবারিক আদালত, ঢাকা" },
    caseType: { en: "Family", bn: "পারিবারিক" },
    hearingNumber: 4,
    status: "closed",
    stages: [
      { ...matterStages[0], date: { en: "05 Mar", bn: "৫ মার্চ" } },
      { ...matterStages[1], date: { en: "18 Mar", bn: "১৮ মার্চ" } },
      { ...matterStages[2], date: { en: "20 Jun", bn: "২০ জুন" } },
      { ...matterStages[3], date: { en: "02 Sep", bn: "২ সেপ্টেম্বর" } },
      { ...matterStages[4], date: { en: "14 Nov 2024", bn: "১৪ নভেম্বর ২০২৪" } },
    ],
    currentStageId: "decision",
  },
];

const dhakaDistrict: Localized = {
  en: "Dhaka District Court",
  bn: "ঢাকা জেলা আদালত",
};
const highCourt: Localized = {
  en: "High Court Division",
  bn: "হাইকোর্ট বিভাগ",
};
const arbitration: Localized = {
  en: "Arbitration Tribunal",
  bn: "সালিশি ট্রাইব্যুনাল",
};
const familyCourt: Localized = {
  en: "Family Court, Dhaka",
  bn: "পারিবারিক আদালত, ঢাকা",
};

export const hearings: Record<string, Hearing[]> = {
  "LC-24018": [
    {
      id: "h-24018-1",
      number: 1,
      date: "2024-10-08",
      court: dhakaDistrict,
      summaryStatus: "approved",
      notes: [
        {
          id: "h-24018-1-n1",
          text: "Defendant entered appearance. Next date fixed for framing of issues.",
        },
      ],
    },
    {
      id: "h-24018-2",
      number: 2,
      date: "2024-11-21",
      court: dhakaDistrict,
      summaryStatus: "draft_ready",
      notes: [
        {
          id: "h-24018-2-n1",
          text: "Court framed issues for trial.",
        },
        {
          id: "h-24018-2-n2",
          text: "Four issues framed; two deferred to the next date.",
        },
      ],
    },
    {
      id: "h-24018-3",
      number: 3,
      date: "2025-01-17",
      court: dhakaDistrict,
      summaryStatus: "draft_ready",
      notes: [
        {
          id: "h-24018-3-n1",
          text: "Plaintiff witness examination. Bring the original deed.",
        },
      ],
    },
  ],
  "LC-24012": [
    {
      id: "h-24012-1",
      number: 1,
      date: "2024-12-02",
      court: highCourt,
      summaryStatus: "draft_ready",
      notes: [
        {
          id: "h-24012-1-n1",
          text: "Case transferred to the High Court Division. Parties notified.",
        },
      ],
    },
    {
      id: "h-24012-2",
      number: 2,
      date: "2024-12-20",
      court: highCourt,
      summaryStatus: "draft_ready",
      notes: [
        {
          id: "h-24012-2-n1",
          text: "Interim order hearing scheduled. Certified copy of the deed filed.",
        },
      ],
    },
  ],
  "LC-23997": [
    {
      id: "h-23997-1",
      number: 1,
      date: "2024-08-10",
      court: arbitration,
      summaryStatus: "processing",
      notes: [
        {
          id: "h-23997-1-n1",
          text: "First sitting. Tribunal constituted and parties identified.",
        },
      ],
    },
    {
      id: "h-23997-2",
      number: 2,
      date: "2024-08-22",
      court: arbitration,
      summaryStatus: "processing",
      notes: [
        {
          id: "h-23997-2-n1",
          text: "Procedural timetable agreed. Claimant to file documents.",
        },
      ],
    },
    {
      id: "h-23997-3",
      number: 3,
      date: "2024-10-15",
      court: arbitration,
      summaryStatus: "processing",
      notes: [
        {
          id: "h-23997-3-n1",
          text: "Claimant's documents filed. Respondent sought time to reply.",
        },
      ],
    },
    {
      id: "h-23997-4",
      number: 4,
      date: "2024-12-05",
      court: arbitration,
      summaryStatus: "processing",
      notes: [
        {
          id: "h-23997-4-n1",
          text: "Reply filed. Tribunal directed parties to exchange witness lists.",
        },
      ],
    },
    {
      id: "h-23997-5",
      number: 5,
      date: "2025-01-21",
      court: arbitration,
      summaryStatus: "processing",
      notes: [
        {
          id: "h-23997-5-n1",
          text: "Witness lists due. Hearing on the preliminary objection.",
        },
      ],
    },
  ],
  "LC-23986": [
    {
      id: "h-23986-1",
      number: 1,
      date: "2024-03-05",
      court: familyCourt,
      summaryStatus: "approved",
      notes: [
        {
          id: "h-23986-1-n1",
          text: "First appearance. Parties referred to mediation.",
        },
      ],
    },
    {
      id: "h-23986-2",
      number: 2,
      date: "2024-03-18",
      court: familyCourt,
      summaryStatus: "approved",
      notes: [
        {
          id: "h-23986-2-n1",
          text: "Mediation did not settle the matter. Evidence directions given.",
        },
      ],
    },
    {
      id: "h-23986-3",
      number: 3,
      date: "2024-06-20",
      court: familyCourt,
      summaryStatus: "approved",
      notes: [
        {
          id: "h-23986-3-n1",
          text: "Evidence recorded. Final arguments scheduled.",
        },
      ],
    },
    {
      id: "h-23986-4",
      number: 4,
      date: "2024-09-02",
      court: familyCourt,
      summaryStatus: "approved",
      notes: [
        {
          id: "h-23986-4-n1",
          text: "Final arguments heard. Judgment reserved.",
        },
      ],
    },
  ],
};

export const documents: Record<string, CaseDocument[]> = {
  "LC-24018": [
    {
      id: "doc-24018-1",
      hearingId: "h-24018-1",
      name: "Notice_of_Suit.pdf",
      size: 248000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-24018-2",
      hearingId: "h-24018-2",
      name: "Written_Statement.pdf",
      size: 512000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-24018-3",
      hearingId: "h-24018-2",
      name: "Witness_List.pdf",
      size: 96000,
      mimeType: "application/pdf",
      status: "failed",
    },
    {
      id: "doc-24018-4",
      hearingId: "h-24018-3",
      name: "Deed_of_Sale.pdf",
      size: 3400000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-24018-5",
      hearingId: "h-24018-3",
      name: "Site_Photo_01.jpg",
      size: 2100000,
      mimeType: "image/jpeg",
      status: "ready",
    },
    {
      id: "doc-24018-6",
      hearingId: "h-24018-3",
      name: "Plaintiff_Affidavit.pdf",
      size: 1250000,
      mimeType: "application/pdf",
      status: "processing",
    },
  ],
  "LC-24012": [
    {
      id: "doc-24012-1",
      hearingId: "h-24012-1",
      name: "Transfer_Order.pdf",
      size: 320000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-24012-2",
      hearingId: "h-24012-2",
      name: "Interim_Order_Copy.pdf",
      size: 410000,
      mimeType: "application/pdf",
      status: "ready",
    },
  ],
  "LC-23997": [
    {
      id: "doc-23997-1",
      hearingId: "h-23997-1",
      name: "Arbitration_Agreement.pdf",
      size: 880000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-23997-2",
      hearingId: "h-23997-3",
      name: "Claimant_Documents.pdf",
      size: 2600000,
      mimeType: "application/pdf",
      status: "ready",
    },
    {
      id: "doc-23997-3",
      hearingId: "h-23997-5",
      name: "Witness_List.pdf",
      size: 140000,
      mimeType: "application/pdf",
      status: "processing",
    },
  ],
  "LC-23986": [
    {
      id: "doc-23986-1",
      hearingId: "h-23986-4",
      name: "Judgment_Copy.pdf",
      size: 1900000,
      mimeType: "application/pdf",
      status: "ready",
    },
  ],
};

export const clients: Client[] = [
  {
    id: "CL-7842-BD",
    name: { en: "Fahim Rahman", bn: "ফাহিম রহমান" },
    phone: "+880 1711-234567",
    email: "fahim.rahman@example.com",
  },
  {
    id: "CL-7851-BD",
    name: { en: "Nusrat Ahmed", bn: "নুসরাত আহমেদ" },
    phone: "+880 1812-345678",
    email: "nusrat.ahmed@example.com",
  },
  {
    id: "CL-7863-BD",
    name: { en: "Rafiq Khan", bn: "রফিক খান" },
    phone: "+880 1913-456789",
    email: "rafiq.khan@example.com",
  },
  {
    id: "CL-7870-BD",
    name: { en: "Samira Sultana", bn: "সামিরা সুলতানা" },
    phone: "+880 1614-567890",
    email: "samira.sultana@example.com",
  },
];

export const activities: Activity[] = [
  {
    id: "activity-document",
    icon: "document",
    title: { en: "Document added", bn: "নথি যোগ হয়েছে" },
    detail: { en: "Witness_Statement.pdf", bn: "সাক্ষীর_বিবৃতি.pdf" },
    time: { en: "18 min ago", bn: "১৮ মিনিট আগে" },
  },
  {
    id: "activity-hearing",
    icon: "calendar",
    title: { en: "Hearing rescheduled", bn: "শুনানির সময় পরিবর্তন" },
    detail: { en: "Ahmed Property Matter", bn: "আহমেদ সম্পত্তি বিষয়ক" },
    time: { en: "2 hours ago", bn: "২ ঘণ্টা আগে" },
  },
  {
    id: "activity-client",
    icon: "clients",
    title: { en: "New client created", bn: "নতুন মক্কেল তৈরি" },
    detail: { en: "Samira Sultana", bn: "সামিরা সুলতানা" },
    time: { en: "Yesterday", bn: "গতকাল" },
  },
];

export const courts: Localized[] = [
  { en: "Dhaka District Court", bn: "ঢাকা জেলা আদালত" },
  { en: "High Court Division", bn: "হাইকোর্ট বিভাগ" },
  { en: "Arbitration Tribunal", bn: "সালিশি ট্রাইব্যুনাল" },
  { en: "Family Court, Dhaka", bn: "পারিবারিক আদালত, ঢাকা" },
];

export const caseTypes: Localized[] = [
  { en: "Property dispute", bn: "সম্পত্তি বিরোধ" },
  { en: "Contract", bn: "চুক্তি" },
  { en: "Family", bn: "পারিবারিক" },
  { en: "Criminal", bn: "ফৌজদারি" },
];
