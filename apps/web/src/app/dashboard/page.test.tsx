import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

// The page reads the signed-in user and the procedures in streamed sections, and those layers
// are server-only, so they are replaced here.
vi.mock("@/lib/server/dal", () => ({
  getCurrentUser: vi.fn(),
  getPatientDrawer: vi.fn(),
  listUpcoming: vi.fn().mockResolvedValue([]),
}));
vi.mock("./demo/actions", () => ({
  openDemoPatient: vi.fn(),
  resetDemo: vi.fn(),
}));
vi.mock("./coordinator/actions", () => ({
  completeTask: vi.fn(),
  confirmStep: vi.fn(),
  releaseSlot: vi.fn(),
  reschedule: vi.fn(),
  resendFailed: vi.fn(),
}));

describe("DashboardPage", () => {
  it("renders the coordinator heading", () => {
    const props = {
      params: Promise.resolve({}),
      searchParams: Promise.resolve({}),
    } as unknown as Parameters<typeof DashboardPage>[0];
    render(<DashboardPage {...props} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Coordinator dashboard" }),
    ).toBeInTheDocument();
  });
});
