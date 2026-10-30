import type { PortalNotification } from "@prefix/shared";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TabBar } from "../shell/tab-bar";
import { UpdatesList } from "./updates-list";

const markNotificationsRead = vi.fn();
const markAllNotificationsRead = vi.fn();
const replace = vi.fn();
let pathname = "/p/updates";

vi.mock("../../actions", () => ({
  markNotificationsRead: (...args: unknown[]) => markNotificationsRead(...args),
  markAllNotificationsRead: () => markAllNotificationsRead(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => pathname,
}));

const NOW = Date.parse("2026-11-10T06:30:00Z");

function update(overrides: Partial<PortalNotification>): PortalNotification {
  return {
    key: "message:1",
    kind: "care_team_message",
    urgency: "normal",
    created_at: "2026-11-10T05:00:00Z",
    read: false,
    appointment_id: null,
    procedure_name: null,
    timezone: null,
    event_id: null,
    step_title: null,
    step_done: false,
    due_at: null,
    scheduled_at: null,
    request_status: null,
    message: "Please bring your medicine list.",
    ...overrides,
  };
}

const CANCELLED = update({
  key: "cancelled:a",
  kind: "appointment_cancelled",
  urgency: "urgent",
  created_at: "2026-11-10T06:00:00Z",
  procedure_name: "Colonoscopy",
  timezone: "Asia/Kolkata",
  scheduled_at: "2026-11-13T04:00:00Z",
  message: null,
});
const MESSAGE = update({});
const DONE = update({
  key: "step-due:e",
  kind: "step_now",
  created_at: "2026-11-09T05:00:00Z",
  read: true,
  step_done: true,
  step_title: "Arrange an escort",
  event_id: "e",
  message: null,
});

beforeEach(() => {
  markNotificationsRead.mockReset().mockResolvedValue({ ok: true });
  markAllNotificationsRead.mockReset().mockResolvedValue({ ok: true });
  replace.mockReset();
  pathname = "/p/updates";
});

function renderList(openKey: string | null = null) {
  render(
    <UpdatesList
      items={[CANCELLED, MESSAGE, DONE]}
      lang="en"
      now={NOW}
      openKey={openKey}
    />,
  );
}

describe("updates", () => {
  it("lists updates newest first and marks the unread ones as new", () => {
    renderList();

    const rows = screen.getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("Your procedure was cancelled"),
      expect.stringContaining("Message from your care team"),
      expect.stringContaining("Done: Arrange an escort"),
    ]);
    expect(within(rows[0]!).getByText("New")).toBeInTheDocument();
    expect(within(rows[2]!).queryByText("New")).not.toBeInTheDocument();
    expect(screen.getByText("2 unread")).toBeInTheDocument();
  });

  it("opens an update in a sheet and marks it read", async () => {
    renderList();

    fireEvent.click(
      screen.getByRole("button", { name: /Message from your care team/ }),
    );

    const sheet = screen.getByRole("dialog", {
      name: "Message from your care team",
    });
    expect(
      within(sheet).getByText("Please bring your medicine list."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(markNotificationsRead).toHaveBeenCalledWith(["message:1"]),
    );
    expect(screen.getByText("1 unread")).toBeInTheDocument();
  });

  it("does not mark an already read update again", () => {
    renderList();

    fireEvent.click(screen.getByRole("button", { name: /Arrange an escort/ }));

    const sheet = screen.getByRole("dialog", {
      name: "Done: Arrange an escort",
    });
    expect(
      within(sheet).getByRole("link", { name: "Go to this step" }),
    ).toHaveAttribute("href", "/p/prep#step-e");
    expect(markNotificationsRead).not.toHaveBeenCalled();
  });

  it("opens the update from the banner and marks it read on arrival", async () => {
    renderList("cancelled:a");

    expect(
      screen.getByRole("dialog", { name: "Your procedure was cancelled" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(markNotificationsRead).toHaveBeenCalledWith(["cancelled:a"]),
    );
  });

  it("marks everything read at once", async () => {
    renderList();

    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));

    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalled());
    expect(screen.queryByText("New")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Mark all as read" }),
    ).not.toBeInTheDocument();
  });

  it("explains an empty feed in Hindi", () => {
    render(<UpdatesList items={[]} lang="hi" now={NOW} openKey={null} />);

    expect(screen.getByText(/अभी कोई अपडेट नहीं है/)).toBeInTheDocument();
  });
});

describe("tab bar", () => {
  it("marks the current tab and announces the unread count", () => {
    render(<TabBar lang="en" unread={3} />);

    const updates = screen.getByRole("link", { name: "Updates, 3 unread" });
    expect(updates).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("is labelled in Hindi", () => {
    pathname = "/p/home";
    render(<TabBar lang="hi" unread={0} />);

    expect(screen.getByRole("link", { name: "होम" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "मेरी तैयारी" })).toHaveAttribute(
      "href",
      "/p/prep",
    );
  });
});
