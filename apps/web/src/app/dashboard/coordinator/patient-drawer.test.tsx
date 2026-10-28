import type { Drawer } from "@prefix/shared";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PatientDrawer } from "./patient-drawer";

vi.mock("./actions", () => ({
  completeTask: vi.fn(),
  confirmStep: vi.fn(),
  releaseSlot: vi.fn(),
  reschedule: vi.fn(),
  resendFailed: vi.fn(),
}));

const APPOINTMENT_ID = "3d1f0c2e-1111-4a2b-9c3d-000000000001";

function drawer(overrides: Partial<Drawer> = {}): Drawer {
  return {
    appointment: {
      appointment_id: APPOINTMENT_ID,
      patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
      patient_name: "Asha Patel",
      procedure_name: "Colonoscopy",
      facility_name: "Demo Main Campus",
      scheduled_at: "2026-10-29T06:00:00Z",
      status: "SCHEDULED",
      readiness: 50,
      required_steps: 2,
      confirmed_steps: 1,
      problem_steps: 0,
      open_escalations: 0,
      open_tasks: 0,
      risk_score: 0,
      risk_level: "LOW",
      risk_reasons: [],
    },
    steps: [
      {
        event_id: "11111111-1111-4111-8111-111111111111",
        title: "Arrange escort",
        status: "SENT",
        due_at: "2026-10-28T06:00:00Z",
        requires_confirmation: true,
        is_critical: false,
        response: null,
      },
      {
        event_id: "22222222-2222-4222-8222-222222222222",
        title: "Low-fibre diet",
        status: "CONFIRMED",
        due_at: "2026-10-26T06:00:00Z",
        requires_confirmation: true,
        is_critical: false,
        response: "YES",
      },
    ],
    messages: [],
    escalations: [],
    tasks: [],
    ...overrides,
  };
}

describe("patient drawer", () => {
  it("offers to mark a step done only while it still needs confirming", () => {
    render(<PatientDrawer drawer={drawer()} filter="all" />);

    const escort = screen.getByText("Arrange escort").closest("li");
    expect(escort).not.toBeNull();
    expect(
      within(escort as HTMLElement).getByRole("button", {
        name: "Mark done for patient",
      }),
    ).toBeInTheDocument();
    const diet = screen.getByText("Low-fibre diet").closest("li");
    expect(
      within(diet as HTMLElement).queryByRole("button", {
        name: "Mark done for patient",
      }),
    ).not.toBeInTheDocument();
  });

  it("requires a reason before a slot can be released", () => {
    render(<PatientDrawer drawer={drawer()} filter="all" />);

    const reason = screen.getByLabelText("Release the slot: reason");
    expect(reason).toBeRequired();
    expect(
      screen.getByRole("button", { name: "Release slot" }),
    ).toBeInTheDocument();
  });

  it("shows the patient's words with the reply, and resend only when something failed", () => {
    render(
      <PatientDrawer
        drawer={drawer({
          steps: [
            {
              event_id: "33333333-3333-4333-8333-333333333333",
              title: "Clear liquids",
              status: "FAILED",
              due_at: "2026-10-27T06:00:00Z",
              requires_confirmation: false,
              is_critical: true,
              response: null,
            },
          ],
        })}
        filter="all"
      />,
    );

    expect(screen.getByText("Failed to send")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Resend failed reminders" }),
    ).toBeInTheDocument();
  });
});
