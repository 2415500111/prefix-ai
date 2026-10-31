"use server";

import type {
  StaffNotificationFeed,
  StaffNotificationSummary,
} from "@prefix/shared";

import { ApiError } from "@/lib/server/api";
import {
  getStaffNotifications,
  getStaffNotificationSummary,
  listUpcoming,
} from "@/lib/server/dal";

import { type ActionResult, refused } from "../action-result";
import { performAction } from "../form-action";

export interface PatientHit {
  appointment_id: string;
  patient_name: string;
  procedure_name: string;
  scheduled_at: string;
}

const SEARCH_HOURS = 168;
const MAX_HITS = 8;

/**
 * Finds patients among the procedures in the next seven days, by name or procedure. Names are
 * encrypted at rest, so the search runs over the list the dashboard is allowed to read anyway.
 */
export async function searchPatients(query: string): Promise<PatientHit[]> {
  const words = query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4);
  if (words.length === 0 || query.length > 100) return [];
  const rows = await listUpcoming(SEARCH_HOURS);
  return rows
    .filter((row) => {
      const text = `${row.patient_name} ${row.procedure_name}`.toLowerCase();
      return words.every((word) => text.includes(word));
    })
    .slice(0, MAX_HITS)
    .map((row) => ({
      appointment_id: row.appointment_id,
      patient_name: row.patient_name,
      procedure_name: row.procedure_name,
      scheduled_at: row.scheduled_at,
    }));
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_IDS = 100;

/**
 * The bell's feed, newest first as the API orders it. Null for a role that cannot see it, so
 * the bell stops asking.
 */
export async function loadStaffNotifications(): Promise<StaffNotificationFeed | null> {
  return orNull(() => getStaffNotifications());
}

/** Totals and the newest id: cheap enough to ask every 15 seconds, and holds no patient data. */
export async function pollStaffNotifications(): Promise<StaffNotificationSummary | null> {
  return orNull(() => getStaffNotificationSummary());
}

/** Mark items read for this person. The pages refresh, so the Overview's red bars follow. */
export async function markStaffNotificationsRead(
  ids: string[],
): Promise<ActionResult> {
  const valid = ids.filter((id) => UUID.test(id));
  if (valid.length === 0 || valid.length > MAX_IDS) {
    return refused("That notification no longer exists.");
  }
  return performAction(
    "/notifications/read",
    { method: "POST", body: { ids: valid } },
    "Marked as read",
  );
}

export async function markAllStaffNotificationsRead(): Promise<ActionResult> {
  return performAction(
    "/notifications/read-all",
    { method: "POST" },
    "All notifications marked as read",
  );
}

async function orNull<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return null;
    throw error;
  }
}
