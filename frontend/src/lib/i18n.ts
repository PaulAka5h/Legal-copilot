export type Language = "en" | "bn";

const en = {
  brand: {
    name: "Legal Copilot",
    tagline: "Legal workspace",
  },
  common: {
    languageEn: "EN",
    languageBn: "বাংলা",
    privateSecure: "Private & secure",
    mockNotice: "Mock sign-in — development only. No password is checked.",
    mockDisabled: "NOT_CONFIGURED — Mock sign-in is disabled. Set MOCK_AUTH=true in .env.local.",
    signOut: "Sign out",
  },
  meta: {
    lawyerLogin: "Lawyer Login",
    clientLogin: "Client Login",
    lawyerDashboard: "Lawyer Dashboard",
    lawyerMatters: "My Matters",
    lawyerClients: "Clients",
    clientDashboard: "Client Dashboard",
  },
  lawyer: {
    builtFor: "Built for Bangladesh",
    headline1: "Practice law.",
    headline2: "Not paperwork.",
    brandCopy: "One calm, secure workspace for every matter, client and hearing.",
    portal: "Lawyer portal",
    welcome: "Welcome back",
    intro: "Sign in to manage your practice.",
    email: "Email address",
    password: "Password",
    remember: "Remember me",
    forgot: "Forgot password?",
    signIn: "Sign in",
    showPassword: "Show password",
    hidePassword: "Hide password",
    switchPrompt: "Are you a client?",
    switchAction: "Client login",
  },
  client: {
    builtFor: "Built for Bangladesh",
    headline1: "Your case,",
    headline2: "clearly explained.",
    brandCopy: "Follow your matter, hearing dates and documents in one secure place.",
    portal: "Client portal",
    title: "View your case",
    intro: "Use the details shared by your lawyer.",
    clientId: "Client ID",
    password: "Password",
    submit: "View my case",
    switchPrompt: "Are you a lawyer?",
    switchAction: "Lawyer login",
    helpTitle: "Your access is private.",
    helpBody: "Contact your lawyer if you need new login details.",
  },
  notConfigured: {
    eyebrow: "Stage 1 stub",
    title: "NOT_CONFIGURED",
    lawyerDashboard: "Lawyer dashboard",
    matters: "My matters",
    clients: "Clients",
    clientDashboard: "Client dashboard",
    body: "This screen is not built yet. Session handling is mock-only and case data is not connected.",
  },
} as const;

type Widen<T> = { [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };

export type Dictionary = Widen<typeof en>;

const bn: Dictionary = {
  brand: {
    name: "Legal Copilot",
    tagline: "আইনি সহায়ক",
  },
  common: {
    languageEn: "EN",
    languageBn: "বাংলা",
    privateSecure: "ব্যক্তিগত ও নিরাপদ",
    mockNotice: "মক লগইন — শুধুমাত্র ডেভেলপমেন্টের জন্য। কোনো পাসওয়ার্ড যাচাই করা হয় না।",
    mockDisabled:
      "NOT_CONFIGURED — মক লগইন বন্ধ আছে। .env.local ফাইলে MOCK_AUTH=true সেট করুন।",
    signOut: "সাইন আউট",
  },
  meta: {
    lawyerLogin: "আইনজীবী লগইন",
    clientLogin: "মক্কেল লগইন",
    lawyerDashboard: "আইনজীবী ড্যাশবোর্ড",
    lawyerMatters: "আমার মামলা",
    lawyerClients: "মক্কেল",
    clientDashboard: "মক্কেল ড্যাশবোর্ড",
  },
  lawyer: {
    builtFor: "বাংলাদেশের জন্য তৈরি",
    headline1: "সহজে মামলা পরিচালনা করুন।",
    headline2: "কাগজপত্র নয়।",
    brandCopy: "প্রতিটি মামলা, মক্কেল ও শুনানির জন্য একটি নিরাপদ কর্মক্ষেত্র।",
    portal: "আইনজীবী পোর্টাল",
    welcome: "স্বাগতম",
    intro: "আপনার কাজ পরিচালনা করতে সাইন ইন করুন।",
    email: "ইমেইল ঠিকানা",
    password: "পাসওয়ার্ড",
    remember: "মনে রাখুন",
    forgot: "পাসওয়ার্ড ভুলে গেছেন?",
    signIn: "সাইন ইন",
    showPassword: "পাসওয়ার্ড দেখুন",
    hidePassword: "পাসওয়ার্ড লুকান",
    switchPrompt: "আপনি কি মক্কেল?",
    switchAction: "মক্কেল লগইন",
  },
  client: {
    builtFor: "বাংলাদেশের জন্য তৈরি",
    headline1: "আপনার মামলা,",
    headline2: "সহজভাবে বুঝুন।",
    brandCopy: "এক নিরাপদ স্থানে আপনার মামলা, শুনানির তারিখ ও নথি দেখুন।",
    portal: "মক্কেল পোর্টাল",
    title: "আপনার মামলা দেখুন",
    intro: "আইনজীবীর দেওয়া তথ্য ব্যবহার করুন।",
    clientId: "মক্কেল আইডি",
    password: "পাসওয়ার্ড",
    submit: "আমার মামলা দেখুন",
    switchPrompt: "আপনি কি আইনজীবী?",
    switchAction: "আইনজীবী লগইন",
    helpTitle: "আপনার প্রবেশাধিকার ব্যক্তিগত।",
    helpBody: "নতুন তথ্যের জন্য আইনজীবীর সাথে যোগাযোগ করুন।",
  },
  notConfigured: {
    eyebrow: "ধাপ ১ স্টাব",
    title: "NOT_CONFIGURED",
    lawyerDashboard: "আইনজীবী ড্যাশবোর্ড",
    matters: "আমার মামলা",
    clients: "মক্কেল",
    clientDashboard: "মক্কেল ড্যাশবোর্ড",
    body: "এই স্ক্রিনটি এখনো তৈরি হয়নি। সেশন শুধুমাত্র মক এবং মামলার তথ্য সংযুক্ত নয়।",
  },
};

export const dictionaries: Record<Language, Dictionary> = { en, bn };

export function titleFor(language: Language, key: keyof Dictionary["meta"]) {
  const copy = dictionaries[language];
  return `${copy.meta[key]} | ${copy.brand.name}`;
}
