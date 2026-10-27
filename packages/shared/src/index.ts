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
