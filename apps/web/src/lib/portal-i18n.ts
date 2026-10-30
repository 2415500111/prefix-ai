import type { StepState } from "@prefix/shared";

/** Languages the portal's own text is written in. Step text comes from the API. */
export const PORTAL_LANGUAGES = ["en", "hi"] as const;
export type PortalLang = (typeof PORTAL_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<PortalLang, string> = {
  en: "English",
  hi: "हिन्दी",
};

export function toPortalLang(value: string | null | undefined): PortalLang {
  return value?.toLowerCase().startsWith("hi") ? "hi" : "en";
}

const LOCALES: Record<PortalLang, string> = { en: "en-IN", hi: "hi-IN" };

interface PortalText {
  greeting: (name: string) => string;
  yourProcedure: string;
  countdown: (relative: string) => string;
  when: string;
  arriveBy: string;
  where: string;
  openMap: string;
  callHospital: string;
  addToCalendar: string;
  checklistTitle: string;
  checklistProgress: (done: number, total: number) => string;
  checklistEmpty: string;
  timelineTitle: string;
  states: Record<StepState, string>;
  important: string;
  confirm: string;
  confirming: string;
  problem: string;
  problemNoteLabel: string;
  sendProblem: string;
  sending: string;
  cancel: string;
  actionFailed: string;
  reschedule: string;
  rescheduleNoteLabel: string;
  rescheduleSend: string;
  rescheduleRequested: string;
  atRisk: string;
  notTranslated: string;
  emergencyTitle: string;
  emergencyText: string;
  noAppointments: string;
  language: string;
  signOut: string;
  askTitle: string;
  askHint: string;
  askLabel: string;
  askSend: string;
  askSending: string;
  askEmpty: string;
  askFailed: string;
  askRateLimited: string;
  askSources: string;
  askHistory: string;
  askDisclaimer: string;
  // App shell
  tabs: Record<PortalTab, string>;
  tabBar: string;
  bell: (unread: number) => string;
  unreadBadge: (unread: number) => string;
  bannerOpen: string;
  bannerDismiss: string;
  close: string;
  // Home
  readinessTitle: string;
  readinessAllDone: string;
  readinessNothing: string;
  nextStepTitle: string;
  noNextStep: string;
  seeFullPlan: string;
  otherProcedures: string;
  // My prep
  prepTitle: string;
  problemSheetTitle: string;
  problemSheetHint: (step: string) => string;
  confirmedToast: string;
  problemSentToast: string;
  // Updates
  updatesTitle: string;
  markAllRead: string;
  noUpdates: string;
  newLabel: string;
  goToStep: string;
  updatesFailed: string;
  // Help
  helpTitle: string;
  emergencyCall: string;
  callHospitalHint: string;
  noHospitalPhone: string;
  rescheduleTitle: string;
  rescheduleHint: string;
  rescheduleSentToast: string;
}

export type PortalTab = "home" | "prep" | "updates" | "help";

export const PORTAL_TEXT: Record<PortalLang, PortalText> = {
  en: {
    greeting: (name) => `Hello, ${name}`,
    yourProcedure: "Your procedure",
    countdown: (relative) => `Your procedure is ${relative}.`,
    when: "When",
    arriveBy: "Please arrive by",
    where: "Where",
    openMap: "Open in maps",
    callHospital: "Call the hospital",
    addToCalendar: "Add to calendar",
    checklistTitle: "Your readiness checklist",
    checklistProgress: (done, total) => `${done} of ${total} done`,
    checklistEmpty: "Nothing to confirm for this procedure.",
    timelineTitle: "Your prep plan",
    states: {
      DONE: "Done",
      DUE: "Do this now",
      UPCOMING: "Coming up",
      OVERDUE: "Overdue",
      ACTIVE: "In effect",
      PROBLEM: "Problem reported",
    },
    important: "Important",
    confirm: "Yes, done",
    confirming: "Saving…",
    problem: "I have a problem",
    problemNoteLabel: "Tell us what is wrong (optional)",
    sendProblem: "Tell my care team",
    sending: "Sending…",
    cancel: "Cancel",
    actionFailed: "That did not work. Please try again or call the hospital.",
    reschedule: "I need to reschedule",
    rescheduleNoteLabel: "Anything we should know? (optional)",
    rescheduleSend: "Ask to reschedule",
    rescheduleRequested:
      "We have asked your care team to call you about a new date.",
    atRisk:
      "Your care team has been told about a problem with your preparation and will contact you.",
    notTranslated:
      "Some steps are shown in English because a Hindi version is not ready yet.",
    emergencyTitle: "Feeling unwell?",
    emergencyText:
      "If you have chest pain, heavy bleeding, fainting, severe stomach pain or a severe allergic reaction, call 112 or go to the nearest emergency department now. For other questions, call your care team.",
    noAppointments: "You have no upcoming procedures.",
    language: "Language",
    signOut: "Sign out",
    askTitle: "Ask about your prep",
    askHint: "Ask a question about the steps in your plan.",
    askLabel: "Your question",
    askSend: "Send question",
    askSending: "Sending…",
    askEmpty: "Please write a question first.",
    askFailed:
      "We could not send your question. Please try again, or call the hospital.",
    askRateLimited:
      "You have asked many questions. Please wait a few minutes and try again.",
    askSources: "Based on these steps",
    askHistory: "Earlier questions",
    askDisclaimer:
      "Answers come only from your prep plan. For anything else, your care team answers.",
    tabs: { home: "Home", prep: "My prep", updates: "Updates", help: "Help" },
    tabBar: "Sections",
    bell: (unread) => (unread > 0 ? `Updates, ${unread} unread` : "Updates"),
    unreadBadge: (unread) => `${unread} unread`,
    bannerOpen: "Open",
    bannerDismiss: "Hide",
    close: "Close",
    readinessTitle: "Your readiness",
    readinessAllDone: "All your steps are done.",
    readinessNothing: "Nothing to confirm yet.",
    nextStepTitle: "Next step",
    noNextStep: "Nothing to do right now. We will remind you.",
    seeFullPlan: "See your full prep plan",
    otherProcedures: "Your other procedures",
    prepTitle: "My prep",
    problemSheetTitle: "Tell us about a problem",
    problemSheetHint: (step) =>
      `${step}. Your care team will see this and contact you.`,
    confirmedToast: "Marked as done",
    problemSentToast: "Your care team has been told",
    updatesTitle: "Updates",
    markAllRead: "Mark all as read",
    noUpdates:
      "No updates yet. We will tell you here when there is something to do.",
    newLabel: "New",
    goToStep: "Go to this step",
    updatesFailed: "We could not update this. Please try again.",
    helpTitle: "Help",
    emergencyCall: "Call 112",
    callHospitalHint: "For questions about your procedure or your prep.",
    noHospitalPhone: "Please use the phone number in your hospital's message.",
    rescheduleTitle: "Change your date",
    rescheduleHint:
      "Ask your care team to move your procedure. They will call you.",
    rescheduleSentToast: "Request sent",
  },
  hi: {
    greeting: (name) => `नमस्ते, ${name}`,
    yourProcedure: "आपकी प्रक्रिया",
    countdown: (relative) => `आपकी प्रक्रिया ${relative} है।`,
    when: "कब",
    arriveBy: "कृपया इस समय तक पहुँचें",
    where: "कहाँ",
    openMap: "नक्शे में खोलें",
    callHospital: "अस्पताल को फ़ोन करें",
    addToCalendar: "कैलेंडर में जोड़ें",
    checklistTitle: "आपकी तैयारी की चेकलिस्ट",
    checklistProgress: (done, total) => `${total} में से ${done} पूरे`,
    checklistEmpty: "इस प्रक्रिया के लिए कुछ भी पुष्टि करने की ज़रूरत नहीं है।",
    timelineTitle: "आपकी तैयारी की योजना",
    states: {
      DONE: "पूरा हुआ",
      DUE: "अभी करें",
      UPCOMING: "आने वाला",
      OVERDUE: "समय निकल गया",
      ACTIVE: "अब लागू है",
      PROBLEM: "समस्या बताई गई",
    },
    important: "ज़रूरी",
    confirm: "हाँ, हो गया",
    confirming: "सहेजा जा रहा है…",
    problem: "मुझे समस्या है",
    problemNoteLabel: "बताइए क्या समस्या है (वैकल्पिक)",
    sendProblem: "मेरी देखभाल टीम को बताएँ",
    sending: "भेजा जा रहा है…",
    cancel: "रद्द करें",
    actionFailed:
      "यह नहीं हो पाया। कृपया फिर से कोशिश करें या अस्पताल को फ़ोन करें।",
    reschedule: "मुझे तारीख बदलनी है",
    rescheduleNoteLabel: "कुछ और बताना चाहें? (वैकल्पिक)",
    rescheduleSend: "तारीख बदलने का अनुरोध भेजें",
    rescheduleRequested:
      "हमने आपकी देखभाल टीम से नई तारीख के लिए आपको फ़ोन करने को कहा है।",
    atRisk:
      "आपकी देखभाल टीम को आपकी तैयारी की समस्या के बारे में बता दिया गया है, वे आपसे संपर्क करेंगे।",
    notTranslated:
      "कुछ चरण अंग्रेज़ी में दिखाए गए हैं क्योंकि उनका हिंदी अनुवाद अभी तैयार नहीं है।",
    emergencyTitle: "तबीयत ठीक नहीं लग रही?",
    emergencyText:
      "अगर आपको सीने में दर्द, ज़्यादा खून बहना, बेहोशी, पेट में तेज़ दर्द या गंभीर एलर्जी हो, तो अभी 112 पर फ़ोन करें या नज़दीकी इमरजेंसी विभाग में जाएँ। दूसरे सवालों के लिए अपनी देखभाल टीम को फ़ोन करें।",
    noAppointments: "आपकी कोई आने वाली प्रक्रिया नहीं है।",
    language: "भाषा",
    signOut: "साइन आउट",
    askTitle: "तैयारी के बारे में पूछें",
    askHint: "अपनी योजना के चरणों के बारे में सवाल पूछें।",
    askLabel: "आपका सवाल",
    askSend: "सवाल भेजें",
    askSending: "भेजा जा रहा है…",
    askEmpty: "पहले कोई सवाल लिखें।",
    askFailed:
      "आपका सवाल नहीं भेजा जा सका। कृपया फिर से कोशिश करें या अस्पताल को फ़ोन करें।",
    askRateLimited:
      "आपने बहुत सारे सवाल पूछे हैं। कृपया कुछ मिनट बाद फिर से कोशिश करें।",
    askSources: "इन चरणों के आधार पर",
    askHistory: "पहले के सवाल",
    askDisclaimer:
      "जवाब केवल आपकी तैयारी की योजना से आते हैं। बाकी सवालों के जवाब आपकी देखभाल टीम देगी।",
    tabs: { home: "होम", prep: "मेरी तैयारी", updates: "अपडेट", help: "मदद" },
    tabBar: "हिस्से",
    bell: (unread) => (unread > 0 ? `अपडेट, ${unread} नहीं पढ़े` : "अपडेट"),
    unreadBadge: (unread) => `${unread} नहीं पढ़े`,
    bannerOpen: "खोलें",
    bannerDismiss: "छिपाएँ",
    close: "बंद करें",
    readinessTitle: "आपकी तैयारी",
    readinessAllDone: "आपके सभी चरण पूरे हो गए हैं।",
    readinessNothing: "अभी पुष्टि करने के लिए कुछ नहीं है।",
    nextStepTitle: "अगला चरण",
    noNextStep: "अभी कुछ करने की ज़रूरत नहीं है। हम आपको याद दिलाएँगे।",
    seeFullPlan: "पूरी तैयारी योजना देखें",
    otherProcedures: "आपकी दूसरी प्रक्रियाएँ",
    prepTitle: "मेरी तैयारी",
    problemSheetTitle: "समस्या के बारे में बताएँ",
    problemSheetHint: (step) =>
      `${step}। आपकी देखभाल टीम इसे देखेगी और आपसे संपर्क करेगी।`,
    confirmedToast: "पूरा दर्ज किया गया",
    problemSentToast: "आपकी देखभाल टीम को बता दिया गया है",
    updatesTitle: "अपडेट",
    markAllRead: "सभी को पढ़ा हुआ करें",
    noUpdates: "अभी कोई अपडेट नहीं है। कुछ करना होगा तो हम आपको यहाँ बताएँगे।",
    newLabel: "नया",
    goToStep: "इस चरण पर जाएँ",
    updatesFailed: "यह अपडेट नहीं हो पाया। कृपया फिर से कोशिश करें।",
    helpTitle: "मदद",
    emergencyCall: "112 पर फ़ोन करें",
    callHospitalHint: "अपनी प्रक्रिया या तैयारी के बारे में सवालों के लिए।",
    noHospitalPhone:
      "कृपया अस्पताल के संदेश में दिया गया फ़ोन नंबर इस्तेमाल करें।",
    rescheduleTitle: "तारीख बदलें",
    rescheduleHint:
      "अपनी देखभाल टीम से प्रक्रिया की तारीख बदलने को कहें। वे आपको फ़ोन करेंगे।",
    rescheduleSentToast: "अनुरोध भेज दिया गया",
  },
};

/** Date and time in the facility's timezone, e.g. "Fri, 14 Nov, 8:30 am". */
export function formatDateTime(
  iso: string,
  timeZone: string,
  lang: PortalLang,
): string {
  return new Intl.DateTimeFormat(LOCALES[lang], {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

export function formatTime(
  iso: string,
  timeZone: string,
  lang: PortalLang,
): string {
  return new Intl.DateTimeFormat(LOCALES[lang], {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "in 3 days", "2 hours ago", "3 दिन में"… Whole days beyond 36 hours. */
export function formatRelative(
  iso: string,
  now: number,
  lang: PortalLang,
): string {
  const diff = new Date(iso).getTime() - now;
  const format = new Intl.RelativeTimeFormat(LOCALES[lang], {
    numeric: "auto",
  });
  const size = Math.abs(diff);
  if (size < HOUR) return format.format(Math.round(diff / MINUTE), "minute");
  if (size < 36 * HOUR) return format.format(Math.round(diff / HOUR), "hour");
  return format.format(Math.round(diff / DAY), "day");
}
