import type { EscalationItem } from "@prefix/shared";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InboxList } from "./inbox-list";

vi.mock("./actions", () => ({
  acknowledgeEscalation: vi.fn(),
  resolveEscalation: vi.fn(),
}));

function item(overrides: Partial<EscalationItem>): EscalationItem {
  return {
    id: "3d1f0c2e-1111-4a2b-9c3d-000000000001",
    patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
    patient_name: "Asha Patel",
    appointment_id: null,
    procedure_name: "Colonoscopy",
    scheduled_at: "2026-11-02T04:30:00Z",
    timezone: "Asia/Kolkata",
    source: "RED_FLAG",
    severity: "URGENT",
    status: "OPEN",
    summary: "Red-flag words: CHEST_PAIN\nPatient asked: chest pain",
    created_at: "2026-10-28T06:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
    resolution_note: null,
    urgent: true,
    urgent_reasons: ["red_flag"],
    ...overrides,
  };
}

describe("nurse inbox", () => {
  it("says so when nothing needs a person", () => {
    render(<InboxList items={[]} />);

    expect(
      screen.getByText("Nothing needs a person right now."),
    ).toBeInTheDocument();
  });

  it("marks urgency in words and shows the patient, procedure and time raised", () => {
    render(<InboxList items={[item({})]} />);

    const card = screen.getByRole("listitem");
    expect(within(card).getByText("Urgent")).toBeInTheDocument();
    expect(within(card).getByText("Red flag")).toBeInTheDocument();
    expect(card).toHaveClass("border-l-urgent");
    expect(
      screen.getByRole("heading", { name: "Asha Patel · Colonoscopy" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/chest pain/)).toBeInTheDocument();
    // In the facility's time zone (IST), with how long ago.
    expect(within(card).getByText("28 Oct, 11:30 am")).toBeInTheDocument();
    expect(within(card).getByText(/ago$/)).toBeInTheDocument();
  });

  it("keeps normal items neutral and in the order given (newest first)", () => {
    render(
      <InboxList
        items={[
          item({
            id: "3d1f0c2e-1111-4a2b-9c3d-000000000003",
            patient_name: "Neha Rao",
            created_at: "2026-10-28T06:02:00Z",
            urgent: false,
            urgent_reasons: [],
          }),
          item({ created_at: "2026-10-28T06:00:00Z" }),
        ]}
      />,
    );

    const [newer, older] = screen.getAllByRole("listitem");
    expect(within(newer).getByRole("heading")).toHaveTextContent("Neha Rao");
    expect(within(newer).queryByText("Urgent")).not.toBeInTheDocument();
    expect(newer).not.toHaveClass("border-l-urgent");
    expect(within(older).getByText("Urgent")).toBeInTheDocument();
  });

  it("offers acknowledge only while waiting, and a required resolution note", () => {
    render(<InboxList items={[item({ status: "OPEN" })]} />);

    expect(
      screen.getByRole("button", { name: "I have this" }),
    ).toBeInTheDocument();
    const note = screen.getByLabelText("What did you do?");
    expect(note).toBeRequired();
    expect(
      screen.getByRole("button", { name: "Mark resolved" }),
    ).toBeInTheDocument();
  });

  it("does not offer acknowledge once it is in hand", () => {
    render(<InboxList items={[item({ status: "ACKNOWLEDGED" })]} />);

    expect(
      screen.queryByRole("button", { name: "I have this" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("In hand")).toBeInTheDocument();
  });

  it("shows the resolution for a resolved escalation and no actions", () => {
    render(
      <InboxList
        items={[
          item({
            status: "RESOLVED",
            resolution_note: "Spoke to the patient.",
          }),
        ]}
      />,
    );

    const card = screen.getByRole("listitem");
    expect(within(card).getByText("Spoke to the patient.")).toBeInTheDocument();
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });
});
