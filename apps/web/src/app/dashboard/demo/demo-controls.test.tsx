import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DemoControls } from "./demo-controls";

const openDemoPatient = vi.fn();
const resetDemo = vi.fn();

vi.mock("./actions", () => ({
  openDemoPatient: (...args: unknown[]) => openDemoPatient(...args),
  resetDemo: (...args: unknown[]) => resetDemo(...args),
}));

describe("demo controls", () => {
  it("offers reset only to the demo's admin", () => {
    const { unmount } = render(<DemoControls isAdmin={false} />);
    expect(
      screen.queryByRole("button", { name: "Reset demo" }),
    ).not.toBeInTheDocument();
    unmount();

    render(<DemoControls isAdmin />);
    expect(
      screen.getByRole("button", { name: "Reset demo" }),
    ).toBeInTheDocument();
  });

  it("opens a demo patient in a new tab, in the chosen language", async () => {
    openDemoPatient.mockResolvedValue({
      ok: true,
      url: "http://localhost:3000/p#token=abc",
      message: "Opened a demo patient (Priya Test) in a new tab.",
    });
    const tab = {
      location: { href: "" },
      opener: undefined as unknown,
      close: vi.fn(),
    };
    const open = vi
      .spyOn(window, "open")
      .mockImplementation(() => tab as unknown as Window);
    render(<DemoControls isAdmin={false} />);

    fireEvent.click(
      screen.getByRole("button", { name: "View patient demo (Hindi)" }),
    );

    await waitFor(() =>
      expect(tab.location.href).toBe("http://localhost:3000/p#token=abc"),
    );
    expect(open).toHaveBeenCalledWith("", "_blank");
    expect(openDemoPatient).toHaveBeenCalledWith("hi");
    open.mockRestore();
  });

  it("shows the reason when the demo cannot open a patient", async () => {
    openDemoPatient.mockResolvedValue({
      ok: false,
      message: "Your role cannot do this.",
    });
    render(<DemoControls isAdmin={false} />);

    fireEvent.click(
      screen.getByRole("button", { name: "View patient demo (English)" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your role cannot do this.",
    );
  });
});
