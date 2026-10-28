// Hand-written until types are generated from the API's OpenAPI schema (Phase 8); keep in
// sync with apps/api/src/prefix_api/schemas/.
export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
}

export type Role =
  "ADMIN" | "COORDINATOR" | "NURSE" | "CLINICIAN" | "VIEWER" | "DEMO_VIEWER";

export interface Me {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface TokenPair {
  access_token: string;
  access_expires_at: string;
  refresh_token: string;
  refresh_expires_at: string;
}

export interface ProcedureType {
  id: string;
  code: string;
  name: string;
  default_duration_minutes: number;
}

export type ProtocolStatus = "DRAFT" | "APPROVED" | "RETIRED";

export const STEP_CATEGORIES = [
  "DIET",
  "FASTING",
  "MEDICATION",
  "BOWEL_PREP",
  "LAB",
  "LOGISTICS",
  "PAPERWORK",
] as const;
export type StepCategory = (typeof STEP_CATEGORIES)[number];

/** JSON rule deciding whether a step applies; see apps/api/.../domain/conditions.py. */
export type Condition = { [key: string]: unknown };

export interface StepInput {
  offset_minutes: number;
  title: string;
  instruction_text: string;
  category: StepCategory;
  requires_confirmation: boolean;
  is_critical: boolean;
  conditions: Condition | null;
}

export interface Step extends StepInput {
  id: string;
  sort_order: number;
}

export interface ProtocolSummary {
  id: string;
  family_id: string;
  version: number;
  procedure_type_id: string;
  name: string;
  status: ProtocolStatus;
  is_sample: boolean;
  approved_at: string | null;
  updated_at: string;
}

export interface Protocol extends ProtocolSummary {
  description: string | null;
  approved_by_id: string | null;
  steps: Step[];
}

export interface ProtocolInput {
  procedure_type_id: string;
  name: string;
  description: string | null;
  steps: StepInput[];
}

export interface ApiErrorBody {
  detail: string | { msg: string; loc: (string | number)[] }[];
  code?: string;
}

/* Patient portal (see apps/api/src/prefix_api/schemas/portal.py). */

export type StepState =
  "DONE" | "DUE" | "UPCOMING" | "OVERDUE" | "ACTIVE" | "PROBLEM";

export type AppointmentStatus =
  "SCHEDULED" | "READY" | "AT_RISK" | "CANCELLED" | "COMPLETED";

export interface PortalFacility {
  name: string;
  address: string | null;
  maps_url: string | null;
  phone: string | null;
  timezone: string;
}

export interface PortalStep {
  event_id: string;
  title: string;
  instruction: string;
  /** Language of title and instruction; "en" when no translation exists yet. */
  language: string;
  category: StepCategory;
  is_critical: boolean;
  requires_confirmation: boolean;
  due_at: string;
  state: StepState;
  can_confirm: boolean;
  can_report_problem: boolean;
}

export interface PortalAppointment {
  id: string;
  procedure_name: string;
  scheduled_at: string;
  arrival_at: string | null;
  duration_minutes: number;
  status: AppointmentStatus;
  facility: PortalFacility;
  steps: PortalStep[];
  reschedule_requested: boolean;
}

export interface PatientSelf {
  id: string;
  first_name: string;
  preferred_language: string;
  preferred_channel: string;
  consent_to_message: boolean;
}

export interface PatientSession {
  access_token: string;
  token_type: string;
  expires_at: string;
}

/* AI Prep Assistant and nurse inbox (see apps/api/src/prefix_api/schemas). */

export type AssistantOutcome =
  | "ANSWERED"
  | "RED_FLAG"
  | "OUT_OF_PROTOCOL"
  | "NOT_COVERED"
  | "CHECK_FAILED"
  | "UNAVAILABLE";

export interface AssistantCitation {
  event_id: string;
  title: string;
}

export interface AssistantReply {
  id: string;
  question: string;
  reply: string;
  outcome: AssistantOutcome;
  /** True when the question went to a nurse instead of being answered. */
  escalated: boolean;
  citations: AssistantCitation[];
  created_at: string;
}

export type EscalationSeverity = "URGENT" | "HIGH" | "NORMAL";
export type EscalationStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

export interface EscalationItem {
  id: string;
  patient_id: string;
  patient_name: string;
  appointment_id: string | null;
  procedure_name: string | null;
  source: string;
  severity: EscalationSeverity;
  status: EscalationStatus;
  summary: string;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
}

/* Guest demo (see apps/api/src/prefix_api/schemas/demo.py). */

export interface Capabilities {
  guest_login: boolean;
}

export interface DemoPatientLink {
  url: string;
  patient_name: string;
  language: "en" | "hi";
}

/* Coordinator dashboard (see apps/api/src/prefix_api/schemas/dashboard.py). */

export type Sla = "overdue" | "due_soon" | "on_time";

export interface UpcomingRow {
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  procedure_name: string;
  facility_name: string;
  scheduled_at: string;
  status: string;
  readiness: number;
  required_steps: number;
  confirmed_steps: number;
  problem_steps: number;
  open_escalations: number;
  open_tasks: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  /** The reasons behind the risk, strongest first, in plain words. */
  risk_reasons: string[];
}

export interface DrawerStep {
  event_id: string;
  title: string;
  status: string;
  due_at: string;
  requires_confirmation: boolean;
  is_critical: boolean;
  response: string | null;
}

export interface DrawerMessage {
  id: string;
  channel: string;
  direction: "INBOUND" | "OUTBOUND";
  status: string;
  body: string;
  error: string | null;
  created_at: string;
}

export interface DrawerEscalation {
  id: string;
  severity: EscalationSeverity;
  status: EscalationStatus;
  summary: string;
  created_at: string;
}

export interface DrawerTask {
  id: string;
  type: string;
  title: string;
  status: string;
  due_at: string | null;
}

export interface Drawer {
  appointment: UpcomingRow;
  steps: DrawerStep[];
  messages: DrawerMessage[];
  escalations: DrawerEscalation[];
  tasks: DrawerTask[];
}

export interface QueueItem {
  id: string;
  type: string;
  title: string;
  status: string;
  patient_id: string | null;
  patient_name: string;
  appointment_id: string | null;
  due_at: string | null;
  sla: Sla;
}

/* Analytics (see apps/api/src/prefix_api/schemas/analytics.py). */

export interface AnalyticsSummary {
  start: string;
  end: string;
  procedures: number;
  cancelled: number;
  cancellation_rate: number | null;
  prep_cancelled: number;
  prep_share: number | null;
  checkins_sent: number;
  checkins_answered: number;
  response_rate: number | null;
  or_minutes_at_risk: number;
  /** A decimal string, to avoid floating-point money. */
  or_cost_at_risk: string;
  baseline_rate: number | null;
  avoided_estimate: number | null;
  or_minutes_saved_estimate: number | null;
  or_cost_saved_estimate: string | null;
}

/* Patients and the waitlist (see apps/api/src/prefix_api/schemas/waitlist.py). */

export interface PatientSummary {
  id: string;
  first_name: string;
  last_name: string;
}

export type WaitlistStatus = "ACTIVE" | "OFFERED" | "BOOKED" | "REMOVED";
export type OfferStatus = "OPEN" | "ACCEPTED" | "DECLINED";

export interface WaitlistEntry {
  id: string;
  patient_id: string;
  patient_name: string;
  procedure_name: string;
  earliest_date: string;
  latest_date: string;
  priority: number;
  status: WaitlistStatus;
}

export interface Offer {
  id: string;
  status: OfferStatus;
  waitlist_entry_id: string;
  patient_id: string;
  patient_name: string;
  /** Why this patient fits the slot, as shown when the offer was made. */
  reasons: string[];
}

export interface ReleasedSlot {
  appointment_id: string;
  procedure_name: string;
  facility_name: string;
  scheduled_at: string;
  open_offer: Offer | null;
}

/* CSV imports (see apps/api/src/prefix_api/schemas/imports.py). */

export type ImportKind = "patients" | "appointments";

export interface ImportRowError {
  /** The line in the file, counting the header as line 1. */
  line: number;
  column: string | null;
  /** Never includes the cell's value. */
  message: string;
}

export interface ImportReport {
  kind: ImportKind;
  rows: number;
  valid_rows: number;
  imported: number;
  committed: boolean;
  ignored_columns: string[];
  errors: ImportRowError[];
}
