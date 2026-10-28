import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

// The page reads the signed-in user in a streamed section; the layer itself is server-only.
vi.mock("@/lib/server/dal", () => ({ getCurrentUser: vi.fn() }));
vi.mock("./demo/actions", () => ({
  openDemoPatient: vi.fn(),
  resetDemo: vi.fn(),
}));

describe("DashboardPage", () => {
  it("renders the empty state", () => {
    render(<DashboardPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Coordinator dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No upcoming procedures")).toBeInTheDocument();
  });
});
