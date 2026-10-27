import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("shows the product name and links to the dashboard", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Prefix AI" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open coordinator dashboard" }),
    ).toHaveAttribute("href", "/dashboard");
  });
});
