import type {
  Activity,
  Client,
  LawyerProfile,
  Localized,
  Matter,
} from "@/lib/api/lawyer";

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
  },
];

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
