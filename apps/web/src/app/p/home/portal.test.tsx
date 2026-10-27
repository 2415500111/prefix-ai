import type { PortalAppointment, PortalStep } from "@prefix/shared";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { readToken } from "../redeem-link";
import { AppointmentCard } from "./appointment-card";
import { Checklist, PrepTimeline } from "./prep-steps";

vi.mock("../actions", () => ({
  confirmStep: vi.fn().mockResolvedValue({ ok: true }),
  reportProblem: vi.fn().mockResolvedValue({ ok: true }),
  requestReschedule: vi.fn().mockResolvedValue({ ok: true }),
  redeemMagicLink: vi.fn(),
}));

const NOW = Date.parse("2026-11-10T06:30:00Z");

function step(overrides: Partial<PortalStep>): PortalStep {
  return {
    event_id: crypto.randomUUID(),
    title: "Arrange escort",
    instruction: "Ask an adult to take you home.",
    language: "en",
    category: "LOGISTICS",
    is_critical: false,
    requires_confirmation: true,
    due_at: "2026-11-12T06:30:00Z",
    state: "UPCOMING",
    can_confirm: false,
    can_report_problem: true,
    ...overrides,
  };
}

const APPOINTMENT: PortalAppointment = {
  id: "0b0c3f1e-8f6a-4c55-9a43-6f0b8f9c1d2e",
  procedure_name: "Colonoscopy",
  scheduled_at: "2026-11-13T04:00:00Z",
  arrival_at: "2026-11-13T03:00:00Z",
  duration_minutes: 45,
  status: "SCHEDULED",
  facility: {
    name: "City Hospital",
    address: "Ring Road",
    maps_url: "https://maps.example.com/city",
    phone: "+911100000000",
    timezone: "Asia/Kolkata",
  },
  steps: [],
  reschedule_requested: false,
};

describe("magic link", () => {
  it("reads the token from the URL fragment", () => {
    expect(readToken("#token=abc_DEF-123")).toBe("abc_DEF-123");
    expect(readToken("")).toBeNull();
  });
});

describe("appointment card", () => {
  it("shows when and where, with calendar, map and phone links", () => {
    render(<AppointmentCard appointment={APPOINTMENT} lang="en" now={NOW} />);

    expect(
      screen.getByRole("heading", { name: "Colonoscopy" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Your procedure is in 3 days."),
    ).toBeInTheDocument();
    expect(screen.getByText(/9:30/)).toBeInTheDocument(); // arrival, Kolkata time
    expect(
      screen.getByRole("link", { name: "Add to calendar" }),
    ).toHaveAttribute("href", `/p/calendar/${APPOINTMENT.id}`);
    expect(screen.getByRole("link", { name: "Open in maps" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
    expect(
      screen.getByRole("link", { name: "Call the hospital" }),
    ).toHaveAttribute("href", "tel:+911100000000");
  });

  it("opens the reschedule form, or says a request was sent", () => {
    const { unmount } = render(
      <AppointmentCard appointment={APPOINTMENT} lang="en" now={NOW} />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "I need to reschedule" }),
    );
    expect(
      screen.getByLabelText("Anything we should know? (optional)"),
    ).toBeInTheDocument();
    unmount();

    render(
      <AppointmentCard
        appointment={{ ...APPOINTMENT, reschedule_requested: true }}
        lang="en"
        now={NOW}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "I need to reschedule" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/call you/);
  });

  it("tells an at-risk patient that the care team will be in touch, in Hindi", () => {
    render(
      <AppointmentCard
        appointment={{ ...APPOINTMENT, status: "AT_RISK" }}
        lang="hi"
        now={NOW}
      />,
    );

    expect(screen.getByText(/देखभाल टीम को आपकी तैयारी/)).toBeInTheDocument();
    expect(
      screen.getByText("आपकी प्रक्रिया 3 दिन में है।"),
    ).toBeInTheDocument();
  });
});

describe("checklist", () => {
  it("counts only steps that need confirmation", () => {
    render(
      <Checklist
        appointmentId={APPOINTMENT.id}
        lang="en"
        steps={[
          step({ title: "Escort", state: "DONE" }),
          step({ title: "Prep solution", state: "DUE" }),
          step({ title: "Diet", requires_confirmation: false }),
        ]}
      />,
    );

    expect(screen.getByText("1 of 2 done")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "1",
    );
    expect(screen.queryByText("Diet")).not.toBeInTheDocument();
  });
});

describe("prep timeline", () => {
  function renderTimeline(steps: PortalStep[], lang: "en" | "hi" = "en") {
    render(
      <PrepTimeline
        appointmentId={APPOINTMENT.id}
        steps={steps}
        timeZone="Asia/Kolkata"
        lang={lang}
        now={NOW}
      />,
    );
  }

  it("offers Confirm only when the step can be confirmed", () => {
    renderTimeline([
      step({ title: "Escort", state: "DUE", can_confirm: true }),
      step({ title: "Liquids", state: "UPCOMING" }),
    ]);

    const [escort, liquids] = screen.getAllByRole("listitem");
    expect(
      within(escort!).getByRole("button", { name: "Yes, done: Escort" }),
    ).toBeInTheDocument();
    expect(
      within(liquids!).queryByRole("button", { name: /Yes, done/ }),
    ).not.toBeInTheDocument();
    expect(
      within(liquids!).getByRole("button", {
        name: "No / I have a problem: Liquids",
      }),
    ).toBeInTheDocument();
  });

  it("asks for an optional note before reporting a problem", () => {
    renderTimeline([step({ title: "Liquids" })]);

    fireEvent.click(screen.getByRole("button", { name: /I have a problem/ }));

    expect(
      screen.getByLabelText("Tell us what is wrong (optional)"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Tell my care team" }),
    ).toBeInTheDocument();
  });

  it("marks critical steps and states with words, not only colour", () => {
    renderTimeline([
      step({ is_critical: true, state: "OVERDUE", can_confirm: true }),
    ]);

    expect(screen.getByText("Important")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });

  it("says when steps are not yet translated", () => {
    renderTimeline([step({ language: "en" })], "hi");

    expect(screen.getByText(/हिंदी अनुवाद अभी तैयार नहीं/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Arrange escort" }),
    ).toHaveAttribute("lang", "en");
  });
});
