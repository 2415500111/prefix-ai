// Hand-written until types are generated from the API's OpenAPI schema (Phase 8); keep in
// sync with apps/api/src/prefix_api/schemas/.
export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
}

export type Role = "ADMIN" | "COORDINATOR" | "NURSE" | "CLINICIAN" | "VIEWER";

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
