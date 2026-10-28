import type { UpcomingRow } from "@prefix/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { filterRows, UpcomingTable } from "./upcoming-table";

function row(overrides: Partial<UpcomingRow>): UpcomingRow {
  return {
    appointment_id: "3d1f0c2e-1111-4a2b-9c3d-000000000001",
    patient_id: "3d1f0c2e-2222-4a2b-9c3d-000000000002",
    patient_name: "Asha Patel",
    procedure_name: "Colonoscopy",
    facility_name: "Demo Main Campus",
    scheduled_at: "2026-10-29T06:00:00Z",
    status: "SCHEDULED",
    readiness: 100,
    required_steps: 2,
    confirmed_steps: 2,
    problem_steps: 0,
    open_escalations: 0,
    open_tasks: 0,
    ...overrides,
  };
}

describe("needs attention filter", () => {
  it("keeps escalations, reported problems and unfinished steps", () => {
    const rows = [
      row({ patient_name: "Ready" }),
      row({ patient_name: "Escalated", open_escalations: 1 }),
      row({ patient_name: "Problem", problem_steps: 1 }),
      row({ patient_name: "Behind", readiness: 50, confirmed_steps: 1 }),
    ];

    expect(filterRows(rows, "all")).toHaveLength(4);
    expect(filterRows(rows, "attention").map((r) => r.patient_name)).toEqual([
      "Escalated",
      "Problem",
      "Behind",
    ]);
  });
});

describe("upcoming table", () => {
  it("says so when nothing needs attention", () => {
    render(<UpcomingTable rows={[]} filter="attention" />);

    expect(
      screen.getByText("Nobody needs attention right now."),
    ).toBeInTheDocument();
  });

  it("shows readiness as words and a number, and links each row to its drawer", () => {
    render(
      <UpcomingTable
        rows={[row({ readiness: 50, confirmed_steps: 1 })]}
        filter="all"
      />,
    );

    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open Asha Patel" }),
    ).toHaveAttribute(
      "href",
      "/dashboard?filter=all&appointment=3d1f0c2e-1111-4a2b-9c3d-000000000001",
    );
  });

  it("names open escalations and tasks in words", () => {
    render(
      <UpcomingTable
        rows={[row({ open_escalations: 2, open_tasks: 1 })]}
        filter="all"
      />,
    );

    expect(screen.getByText("2 escalations")).toBeInTheDocument();
    expect(screen.getByText("1 task")).toBeInTheDocument();
  });
});
