import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DashboardPage from "./page";

describe("DashboardPage", () => {
  it("renders the empty state", () => {
    render(<DashboardPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Coordinator dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No upcoming procedures")).toBeInTheDocument();
  });
});
