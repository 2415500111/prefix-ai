import type { Drawer, DrawerStep, UpcomingRow } from "@prefix/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  buildActivity,
  escortStep,
  PatientSheet,
  permissionsFor,
  stepState,
} from "./patient-sheet";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("./actions", () => ({
  approveRequest: vi.fn(),
  confirmStep: vi.fn(),
  declineRequest: vi.fn(),
  logCall: vi.fn(),
  messagePatient: vi.fn(),
  releaseSlot: vi.fn(),
  reschedule: vi.fn(),
  resendFailed: vi.fn(),
}));

const ROW: UpcomingRow = {
  appointment_id: "3d1f0c2e-1111-4a2b-9c3d-000000000001",
  patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
  patient_name: "Asha Patel",
  procedure_name: "Colonoscopy",
  facility_name: "Demo Main Campus",
  scheduled_at: "2026-11-02T03:30:00Z",
  status: "SCHEDULED",
  readiness: 50,
  required_steps: 2,
  confirmed_steps: 1,
  problem_steps: 0,
  open_escalations: 0,
  open_tasks: 1,
  risk_score: 40,
  risk_level: "MEDIUM",
  risk_reasons: ["Escort not confirmed"],
};

function step(overrides: Partial<DrawerStep>): DrawerStep {
  return {
    event_id: "3d1f0c2e-3333-4a2b-9c3d-000000000003",
    title: "Arrange an escort",
    status: "SENT",
    due_at: "2026-11-01T03:30:00Z",
    requires_confirmation: true,
    is_critical: false,
    response: null,
    confirmed_at: null,
    category: "LOGISTICS",
    ...overrides,
  };
}

function drawer(overrides: Partial<Drawer> = {}): Drawer {
  return {
    appointment: ROW,
    steps: [step({})],
    messages: [],
    escalations: [],
    tasks: [],
    ...overrides,
  };
}

describe("patient sheet logic", () => {
  it("finds the escort step that still needs confirming", () => {
    expect(escortStep([step({})])?.title).toBe("Arrange an escort");
    expect(escortStep([step({ status: "CONFIRMED" })])).toBeUndefined();
    expect(
      escortStep([step({ category: "DIET", title: "Low-fibre diet" })]),
    ).toBeUndefined();
  });

  it("calls a NO or HELP answer a problem, whatever the step's status", () => {
    expect(stepState(step({ response: "HELP" })).label).toBe(
      "Problem reported",
    );
    expect(stepState(step({ status: "CONFIRMED" })).label).toBe("Done");
    expect(stepState(step({ status: "PENDING" })).label).toBe("Coming up");
    expect(stepState(step({ status: "PENDING", state: "OVERDUE" })).label).toBe(
      "Overdue",
    );
    expect(stepState(step({ status: "SENT", state: "DUE" })).label).toBe(
      "Due now",
    );
  });

  it("builds one activity feed, newest first, with plain words", () => {
    const activity = buildActivity(
      drawer({
        steps: [
          step({ status: "CONFIRMED", confirmed_at: "2026-10-30T10:00:00Z" }),
        ],
        messages: [
          {
            id: "m1",
            channel: "SMS",
            direction: "OUTBOUND",
            status: "SENT",
            body: "Reminder",
            error: null,
            created_at: "2026-10-30T08:00:00Z",
          },
          {
            id: "m2",
            channel: "PORTAL",
            direction: "OUTBOUND",
            status: "DELIVERED",
            body: "See you soon",
            error: null,
            created_at: "2026-10-30T12:00:00Z",
            provider: "care_team",
          },
        ],
        tasks: [
          {
            id: "t1",
            type: "RESCHEDULE",
            title: "Patient asked to reschedule",
            status: "CANCELLED",
            due_at: null,
            created_at: "2026-10-30T09:00:00Z",
            completed_at: "2026-10-30T11:00:00Z",
          },
        ],
      }),
    );

    expect(activity.map((entry) => entry.text)).toEqual([
      "Care team message sent",
      "Reschedule declined",
      "Step done: Arrange an escort",
      "Patient asked to reschedule",
      "Reminder sent",
    ]);
  });

  it("lets a guest tick things off but not move or cancel a procedure", () => {
    expect(permissionsFor("DEMO_VIEWER")).toEqual({
      canChange: false,
      canComplete: true,
      canMessage: false,
    });
    expect(permissionsFor("COORDINATOR").canChange).toBe(true);
    expect(permissionsFor("NURSE").canMessage).toBe(true);
  });
});

describe("patient sheet", () => {
  it("opens on the tab a link asks for, e.g. the prep timeline for a problem", async () => {
    render(
      <PatientSheet
        drawer={drawer()}
        filter="all"
        role="COORDINATOR"
        tab="timeline"
      />,
    );

    await screen.findByRole("dialog", { name: "Asha Patel" });
    expect(screen.getByRole("tab", { name: "Prep timeline" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("opens with the patient, tabs and one action bar", async () => {
    render(<PatientSheet drawer={drawer()} filter="all" role="COORDINATOR" />);

    expect(
      await screen.findByRole("dialog", { name: "Asha Patel" }),
    ).toBeInTheDocument();
    for (const name of [
      "Overview",
      "Prep timeline",
      "Messages",
      "Requests",
      "Activity",
    ]) {
      expect(
        screen.getByRole("tab", { name: new RegExp(name) }),
      ).toBeInTheDocument();
    }
    for (const name of [
      "Call logged",
      "Confirm escort",
      "Reschedule",
      "Cancel",
    ]) {
      expect(screen.getByRole("button", { name })).toBeEnabled();
    }
  });

  it("disables what a guest's role cannot do", async () => {
    render(<PatientSheet drawer={drawer()} filter="all" role="DEMO_VIEWER" />);

    await screen.findByRole("dialog", { name: "Asha Patel" });
    expect(screen.getByRole("button", { name: "Call logged" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reschedule" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});
