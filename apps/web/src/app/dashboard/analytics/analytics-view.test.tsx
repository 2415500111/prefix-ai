import type { AnalyticsSummary } from "@prefix/shared";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalyticsView, money, percent } from "./analytics-view";

const BASE: AnalyticsSummary = {
  start: "2026-10-01",
  end: "2026-10-28",
  procedures: 40,
  cancelled: 4,
  cancellation_rate: 10,
  prep_cancelled: 3,
  prep_share: 75,
  checkins_sent: 20,
  checkins_answered: 15,
  response_rate: 75,
  or_minutes_at_risk: 135,
  or_cost_at_risk: "20250.00",
  baseline_rate: null,
  avoided_estimate: null,
  or_minutes_saved_estimate: null,
  or_cost_saved_estimate: null,
};

describe("analytics formatting", () => {
  it("says so when there is nothing to compare, instead of showing a number", () => {
    expect(percent(null)).toBe("No procedures to compare");
    expect(percent(12.5)).toBe("12.5%");
  });

  it("formats OR cost in rupees, and says a baseline is needed when it is missing", () => {
    expect(money(null)).toBe("Needs a baseline");
    expect(money("20250.00")).toMatch(/20,250/);
  });
});

describe("analytics view", () => {
  it("shows the definitions and that slots backfilled is not tracked yet", () => {
    render(<AnalyticsView summary={BASE} />);

    expect(screen.getByText("Not tracked yet")).toBeInTheDocument();
    expect(
      screen.getByText("4 of 40 procedures cancelled"),
    ).toBeInTheDocument();
    expect(screen.getByText(/is exposure to the time/)).toBeInTheDocument();
  });

  it("claims no savings without a baseline", () => {
    render(<AnalyticsView summary={BASE} />);

    expect(screen.getByText(/nothing is claimed as saved/)).toBeInTheDocument();
  });

  it("states the estimate against the baseline the hospital gave", () => {
    render(
      <AnalyticsView
        summary={{
          ...BASE,
          baseline_rate: 15,
          avoided_estimate: 2,
          or_minutes_saved_estimate: 90,
          or_cost_saved_estimate: "13500.00",
        }}
      />,
    );

    expect(screen.getByText(/Against a baseline of 15%/)).toBeInTheDocument();
    expect(screen.getByText("90 minutes")).toBeInTheDocument();
  });
});
