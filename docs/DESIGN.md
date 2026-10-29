# Design

Prefix AI should feel like a calm, trustworthy medical service. Patients use it on a phone the night before a procedure, often anxious. Staff use it all day on a desktop to decide who needs a call. Both apps share one design system, so a coloured pill or an animation means the same thing everywhere.

This document is the reference for the v1.2 redesign. The safety rules in CLAUDE.md are unchanged: the new screens show the same approved protocol content, red flags still go to a human, and every new endpoint is audited.

## 1. Principles

1. **Calm first.** White and soft cool-grey surfaces, one teal-blue accent, colour only where it carries meaning.
2. **Status is always the same colour and always has words.** Green means ready, amber means needs attention, red means high risk or urgent. A colour is never the only signal; there is always a word or an icon beside it.
3. **One place for each job.** Staff navigation is grouped by what you are doing, not by data type (section 4).
4. **Motion explains, never decorates.** Things come from where you tapped and go back there. Nothing blocks a click, and reduced-motion users get instant changes.

## 2. Tokens

Tokens are CSS variables in `apps/web/src/app/globals.css`, mapped to Tailwind utilities with `@theme inline` (Tailwind 4 keeps its configuration in CSS). Components use the utilities (`bg-card`, `text-muted-foreground`, `bg-ready-soft`), never raw colours.

### Colour (light, the default)

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--background` | `#F5F7FA` | App background | text 16.2:1 |
| `--card` | `#FFFFFF` | Cards, sheets, popovers | text 17.4:1 |
| `--muted` | `#EEF2F6` | Quiet fills, skeletons, segmented-control track | muted text 5.7:1 |
| `--foreground` | `#0F1B2A` | Body text | |
| `--muted-foreground` | `#526070` | Secondary text | 6.4:1 on card, 6.0:1 on background |
| `--primary` | `#0B6B85` | Clinical teal-blue: primary buttons, links, focus | white on it 6.1:1 |
| `--primary-soft` / `-foreground` | `#E3F1F5` / `#0A5A70` | Selected items, info pills | 6.7:1 |
| `--ready` / `--ready-soft` / `-foreground` | `#157A4C` / `#E5F5EC` / `#0F5E3A` | Ready, done, low risk | 6.9:1 on soft; white on solid 5.4:1 |
| `--attention` / `--attention-soft` / `-foreground` | `#B45309` / `#FDF2DF` / `#8A3D07` | Needs attention, medium risk | 6.9:1 on soft |
| `--urgent` / `--urgent-soft` / `-foreground` | `#C0282D` / `#FCE9E9` / `#9B1C1F` | High risk, urgent, red flags, destructive actions | 7.0:1 on soft; white on solid 5.9:1 |
| `--border` | `#E2E8EF` | Card and list dividers (decorative) | |
| `--input` | `#7F8C9B` | Input and checkbox borders | 3.4:1, meets the 3:1 rule for controls |
| `--ring` | `#0B6B85` | Focus ring, 2px with 2px offset | 6.1:1 |

### Colour (dark)

Dark mode follows the system setting (`prefers-color-scheme`) and can be forced with a `.dark` class. The same token names hold darker surfaces and lighter accents:

`--background #0B1118`, `--card #121B25`, `--muted #18232F`, `--foreground #E6EDF3` (14.7:1 on card), `--muted-foreground #9AABBC` (7.4:1), `--primary #4DB5CF` with `#04212A` text (7.0:1), ready `#86E0B0` on `#0F2A1E` (9.7:1), attention `#F5C77A` on `#2E2210` (9.9:1), urgent `#F7A3A3` on `#331617` (8.5:1), `--input #5F7184` (3.5:1).

All ratios were measured with the WCAG 2.2 relative-luminance formula. Every text pair is at least 5:1, above the 4.5:1 AA minimum.

### Typography

- **Stack:** `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", Inter, "Segoe UI", Roboto, sans-serif`. Apple devices get SF Pro; everyone else gets Inter, loaded with `next/font` so nothing is fetched from Google at run time.
- **Hindi:** `:lang(hi)` puts Noto Sans Devanagari first, so Hindi text has matching weight and height.
- **Scale (iOS-like):** large title 28/34, title 20/26, headline 17/24 semibold, body 15/22 (staff) and 17/26 (patient portal), footnote 13/18. Numbers use tabular figures so counts do not jump when they animate.

### Shape, depth and glass

- **Radius:** buttons and inputs 12px, cards 16px, sheets and dialogs 20px, pills fully rounded.
- **Shadows (layered, soft):** `--shadow-card` for resting cards, `--shadow-raised` for popovers and toasts, `--shadow-overlay` for sheets and dialogs. Each is two stacked, low-opacity shadows tinted with the foreground colour.
- **Glass:** the top bar, sheets' headers, popovers, toasts and the portal tab bar use `background: color-mix(card 72%, transparent)` with `backdrop-filter: saturate(180%) blur(20px)`, like macOS. Where `backdrop-filter` is unsupported, the surface is opaque.
- **Icons:** lucide, 18px in lists and 20px in navigation, stroke 1.75. Medical meaning first: `Stethoscope`, `ClipboardList`, `CalendarClock`, `HeartPulse`, `BellRing`, `ShieldAlert`.

## 3. Motion

The Motion library (`motion/react`) drives everything with physics. Shared presets live in `apps/web/src/lib/motion.ts`:

| Preset | Spring | Feels like | Used for |
|---|---|---|---|
| `snappy` | stiffness 520, damping 40, mass 0.8 (about 200 ms) | A tap that answers at once | Popovers, toasts, segmented control, tab indicator |
| `gentle` | stiffness 280, damping 32 (about 350 ms) | A sheet settling into place | Dialogs, side sheets, bottom sheets, page entry |
| `ease` | tween 180 ms, iOS curve `[0.32, 0.72, 0, 1]` | Fades | Backdrops, exits, skeleton to content |

Rules:

- **Dialogs and confirmations** open like macOS: scale from 0.96 and fade in, over a backdrop that fades in with a 6px blur. They close faster than they open (150 ms).
- **Side sheets** (patient detail on desktop) slide in from the right with `gentle`. **Bottom sheets** (mobile, and the patient's "I have a problem") slide up and can be dragged down to close: past 120px or a quick flick closes, anything less springs back.
- **Popovers** grow from their trigger (transform origin at the trigger) with `snappy`.
- **Toasts** drop in from the top like iOS notifications, stay four seconds (urgent ones stay until dismissed), and can be swiped up to dismiss. They are announced in a polite live region; failures use an assertive one.
- **Pages** fade in and rise 6px. **Lists** stagger their rows by 30 ms, up to the first ten.
- **Buttons** press to 0.97 scale. This is CSS, so it works in server-rendered buttons without JavaScript.
- **Numbers and progress** (summary cards, readiness bars and rings, risk scores) animate from the old value to the new one.
- **Loading** shows skeletons with the shape of the content, never a blank screen or a spinner alone.
- **Durations** stay between 150 and 350 ms. Animations never block input: a sheet can be closed while it is still opening.
- **Reduced motion** (`prefers-reduced-motion: reduce`) turns movement off. Motion's `MotionConfig reducedMotion="user"` covers springs and a CSS rule covers transitions; things still appear, only without movement.

## 4. Where every feature lives (staff app)

A macOS-style sidebar replaces the top links. It is grouped by the job you are doing:

| Group | Item | Badge | Why it is here |
|---|---|---|---|
| **Today** | Overview | | The day's procedures, least ready first: the home screen. |
| | Tasks | open tasks | Work the system opened for you, to clear today. |
| | Requests | pending reschedule requests | Patients waiting for an answer, which is time-sensitive. |
| **Patients** | Inbox | open escalations | Conversations and red flags about individual patients. |
| | Waitlist | | Matching waiting patients to released slots. |
| **Clinical** | Protocols | | Content owned by clinicians, changed rarely and with sign-off. |
| **Insights** | Analytics | | Looking back, not acting now. |
| **Admin** | Import, Reset demo | | Data loading and demo upkeep. Reset demo appears only for a demo hospital's admin, with a confirmation. |

On phones the sidebar becomes a sheet from the left, opened from the top bar.

**Top bar** (glass): the page title; patient search (searches the next seven days of procedures by name or procedure and opens the patient's sheet); a notifications popover (open escalations, overdue tasks, new reschedule requests, newest first); and the user menu (name, role, sign out). The demo banner stays, as one slim line above the top bar.

**Overview:** four summary cards (procedures in the next 72 hours, high-risk count, open escalations, ready percentage), then the patient list. Risk is a coloured pill with the score and the top two reasons. Filters are a segmented control: All, Needs attention, High risk.

**Patient sheet:** opens from the right over the list (the URL keeps `?appointment=`, so it can be shared and the back button closes it). Tabs:

- **Overview:** readiness, risk and reasons, the next step due, and the action bar.
- **Prep timeline:** every step with its due time and state; staff can mark a step done for the patient.
- **Messages:** reminders sent, patient replies and staff messages, with a box to send the patient a short message. It appears in the patient's Updates.
- **Requests:** this patient's reschedule requests, with Approve (pick the new time) and Decline.
- **Activity:** one time-ordered feed of everything above, plus calls logged, tasks and escalations.

**Action bar**, the same in every tab: **Call logged**, **Confirm escort**, **Reschedule**, **Cancel**. Each opens a confirmation dialog, and Cancel and Reschedule ask for the reason or the new time inside it. Every action, on every page, ends in a toast: green tick on success, red with the reason on failure.

## 5. Patient portal

Mobile-first, like an iOS app, with the same tokens and motion. Body text is 17px and every tap target is at least 48px.

- **Header** (glass): the hospital's name, the English / हिन्दी toggle, and a bell with the unread count.
- **Banner:** the most urgent unread update drops in at the top, for example "Start fasting now". Tapping it opens the update and marks it read.
- **Bottom tab bar** (glass): **Home**, **My prep**, **Updates** (with the unread badge), **Help**.
  - **Home:** the procedure card (countdown, when and where, maps, call, calendar), a readiness ring, and the next step to do now, highlighted.
  - **My prep:** the timeline. Each step has **Yes, done** and **I have a problem**. The problem button opens a bottom sheet with an optional note.
  - **Updates:** the notifications feed (section 6).
  - **Help:** an emergency box (call 112), call the hospital, ask to reschedule, and the assistant. The assistant keeps every safety rule, and without an AI key it stays in nurse hand-off mode.
- Every string is in English and Hindi. Step text uses the approved protocol, translated with the existing cached translations. Times use the facility's timezone.

## 6. Patient notifications (Updates)

**What a patient sees**, newest first:

| Kind | Example | Urgency |
|---|---|---|
| Do this now | "Do this now: Clear liquids only" | Urgent if the step is critical, otherwise normal |
| Coming up | "In 6 hours: Arrange an escort" (steps due in the next 24 hours) | Normal |
| Message from your care team | The text a coordinator sent | Normal |
| Reschedule request | "We received your request" → "Approved: your new time is …" or "We could not move your procedure, please call us" | Normal; approved or declined is urgent |
| Appointment changed | "Your procedure moved to Sat 2 Nov, 9:00" or "Your procedure was cancelled" | Urgent |

**How it is built.** The feed is derived when it is read, from records that already exist: the prep timeline, staff messages, reschedule tasks and the appointment's audited changes. Nothing new runs in the reminder or booking code, so business logic is unchanged. The one new table, `patient_notification_read`, stores which items a patient has read. Each item has a stable key, such as `step-due:<event id>` or `reschedule:<task id>:approved`.

**Endpoints** (patient session only, scoped to the patient):

- `GET /patient/notifications` returns the items with `kind`, `urgency`, `created_at`, `read` and structured `params`, plus `unread_count`.
- `POST /patient/notifications/read` takes a list of keys. Keys that are not in the patient's current feed are refused, so a patient can only mark their own items.
- `POST /patient/notifications/read-all` marks every current item read.

**Text and safety.** The API returns kinds and parameters, not sentences. The portal writes the sentence from a fixed English or Hindi template, so no AI writes notification text (safety rule a). Step titles come from the approved protocol. Staff messages are written by a person. Reading the feed and marking items read are both audited (rule d). Notifications never show red-flag content back to the patient; red flags keep their own emergency reply.

## 7. Other new endpoints

Each one exists because a feature above needs it, and each is audited in its service:

- `GET /dashboard/badges`: counts for the sidebar (open tasks, open escalations, pending reschedule requests).
- `POST /appointments/{id}/calls`: logs a call with the patient, and closes that appointment's open "call patient" tasks.
- `POST /appointments/{id}/messages`: sends the patient a short message that appears in the portal's Updates. It is stored encrypted like every message, and it is never sent by SMS from here.
- `POST /requests/{task id}/approve` (with the new time) reschedules the appointment and marks the request approved. `POST /requests/{task id}/decline` marks it declined. A reschedule request stays a `RESCHEDULE` task: open is pending, done is approved, cancelled is declined.
- The portal's own data gains the hospital name for the header.

## 8. Accessibility

WCAG 2.2 AA throughout: the contrast above; visible focus rings; dialogs and sheets trap focus, close on Escape and return focus to their trigger (Base UI primitives); tabs and segmented controls use arrow keys; toasts are live regions; the bottom tab bar uses `aria-current`; and touch targets are at least 44px (48px in the portal). Playwright runs axe on the staff overview and the portal at desktop and phone sizes.
