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
    source: "RED_FLAG",
    severity: "URGENT",
    status: "OPEN",
    summary: "Red-flag words: CHEST_PAIN\nPatient asked: chest pain",
    created_at: "2026-10-28T06:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
    resolution_note: null,
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

  it("labels severity in words and shows the patient and procedure", () => {
    render(<InboxList items={[item({})]} />);

    expect(screen.getByText("Urgent")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Asha Patel · Colonoscopy" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/chest pain/)).toBeInTheDocument();
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
