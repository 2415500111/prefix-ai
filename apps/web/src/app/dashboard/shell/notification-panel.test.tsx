import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { feed, notification } from "./notification-fixtures";
import { NotificationPanel } from "./notification-panel";

const NEWER = notification({
  id: "019a0000-0000-7000-8000-000000000002",
  patient_name: "Ravi Kumar",
  summary: "Cannot complete: Arrange escort",
  created_at: "2026-10-30T07:34:00Z",
  urgent: false,
  urgent_reasons: [],
});
const OLDER = notification({ created_at: "2026-10-30T07:32:00Z" });

function rows(): HTMLElement[] {
  return within(
    screen.getByRole("list", { name: "Notifications, newest first" }),
  ).getAllByRole("link");
}

describe("staff notification panel", () => {
  it("lists items in the order the API gives (newest first), urgent ones included", () => {
    render(
      <NotificationPanel
        feed={feed([NEWER, OLDER])}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );

    const [first, second] = rows();
    expect(first).toHaveTextContent("Ravi Kumar");
    expect(second).toHaveTextContent("Neha Sharma");
  });

  it("shows who, which procedure, what, and when in the facility's time", () => {
    render(
      <NotificationPanel
        feed={feed([OLDER])}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );

    const [row] = rows();
    expect(row).toHaveTextContent("Neha Sharma");
    expect(row).toHaveTextContent("Colonoscopy");
    expect(row).toHaveTextContent("Cannot complete: Clear liquids");
    expect(within(row).getByText("30 Oct, 1:02 pm")).toHaveAttribute(
      "datetime",
      "2026-10-30T07:32:00Z",
    );
    expect(row).toHaveTextContent(/ago$/);
  });

  it("marks urgent items in red with words, and keeps normal ones neutral", () => {
    render(
      <NotificationPanel
        feed={feed([NEWER, OLDER])}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );

    const [normal, urgent] = rows();
    expect(urgent).toHaveClass("border-l-urgent");
    expect(within(urgent).getByText("Urgent")).toBeInTheDocument();
    expect(normal).not.toHaveClass("border-l-urgent");
    expect(within(normal).queryByText("Urgent")).not.toBeInTheDocument();
  });

  it("puts an unread dot on unread items only", () => {
    render(
      <NotificationPanel
        feed={feed([{ ...NEWER, read: true }, OLDER])}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );

    const [read, unread] = rows();
    expect(within(read).queryByText("Unread")).not.toBeInTheDocument();
    expect(within(unread).getByText("Unread")).toBeInTheDocument();
  });

  it("filters to urgent items with the Urgent only chip", async () => {
    render(
      <NotificationPanel
        feed={feed([NEWER, OLDER])}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );
    const chip = screen.getByRole("button", { name: "Urgent only" });

    fireEvent.click(chip);

    expect(chip).toHaveAttribute("aria-pressed", "true");
    // The hidden row slides out first.
    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(rows()[0]).toHaveTextContent("Neha Sharma");
  });

  it("opens an item on click and offers to mark everything read", () => {
    const onOpen = vi.fn();
    const onMarkAllRead = vi.fn();
    render(
      <NotificationPanel
        feed={feed([OLDER])}
        onOpen={onOpen}
        onMarkAllRead={onMarkAllRead}
      />,
    );

    fireEvent.click(rows()[0]);
    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(onOpen).toHaveBeenCalledWith(OLDER);
    expect(onMarkAllRead).toHaveBeenCalled();
  });

  it("shows a placeholder while the feed loads", () => {
    render(
      <NotificationPanel
        feed={null}
        onOpen={vi.fn()}
        onMarkAllRead={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("status", { name: "Loading notifications" }),
    ).toBeInTheDocument();
  });
});
