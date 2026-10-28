import type { ReleasedSlot, WaitlistEntry } from "@prefix/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReleasedSlotCard } from "./released-slot";
import { WaitlistTable } from "./waitlist-table";

vi.mock("./actions", () => ({
  acceptOffer: vi.fn(),
  declineOffer: vi.fn(),
  findBackfill: vi.fn(),
  removeEntry: vi.fn(),
}));

const OFFER = {
  id: "3d1f0c2e-3333-4a2b-9c3d-000000000003",
  status: "OPEN" as const,
  waitlist_entry_id: "3d1f0c2e-4444-4a2b-9c3d-000000000004",
  patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
  patient_name: "Asha Patel",
  reasons: [
    "Priority 1",
    "Slot date is inside their window (2026-10-30 to 2026-11-01)",
  ],
};

function slot(overrides: Partial<ReleasedSlot> = {}): ReleasedSlot {
  return {
    appointment_id: "3d1f0c2e-1111-4a2b-9c3d-000000000001",
    procedure_name: "Colonoscopy",
    facility_name: "Demo Main Campus",
    scheduled_at: "2026-10-31T06:00:00Z",
    open_offer: null,
    ...overrides,
  };
}

describe("released slot", () => {
  it("lets a coordinator offer the slot when nobody has it yet", () => {
    render(<ReleasedSlotCard slot={slot()} canManage />);

    expect(
      screen.getByRole("button", { name: "Find backfill" }),
    ).toBeInTheDocument();
  });

  it("shows who holds the offer and why, with accept and decline", () => {
    render(<ReleasedSlotCard slot={slot({ open_offer: OFFER })} canManage />);

    expect(screen.getByText("Asha Patel")).toBeInTheDocument();
    expect(screen.getByText("Priority 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
  });

  it("shows viewers the offer without any buttons", () => {
    render(
      <ReleasedSlotCard slot={slot({ open_offer: OFFER })} canManage={false} />,
    );

    expect(screen.getByText("Asha Patel")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("waiting list", () => {
  const entry: WaitlistEntry = {
    id: "3d1f0c2e-5555-4a2b-9c3d-000000000005",
    patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
    patient_name: "Asha Patel",
    procedure_name: "Colonoscopy",
    earliest_date: "2026-10-30",
    latest_date: "2026-11-01",
    priority: 1,
    status: "ACTIVE",
  };

  it("lets a coordinator remove a patient", () => {
    render(<WaitlistTable entries={[entry]} canManage />);

    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("hides the remove button from viewers", () => {
    render(<WaitlistTable entries={[entry]} canManage={false} />);

    expect(screen.getByText("Asha Patel")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
