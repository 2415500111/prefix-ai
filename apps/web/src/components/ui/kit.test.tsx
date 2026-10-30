import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Button } from "./button";
import { ConfirmDialog } from "./dialog";
import { dismissToast, toast, Toaster } from "./toast";

describe("toasts", () => {
  afterEach(() => {
    for (let id = 1; id < 50; id += 1) dismissToast(id);
  });

  it("announces a success politely and a failure as an alert", async () => {
    render(<Toaster />);

    act(() => {
      toast.success("Step confirmed");
      toast.error("Could not reschedule", {
        description: "Try again in a minute.",
      });
    });

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Step confirmed",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Could not reschedule");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Try again in a minute.",
    );
  });

  it("can be dismissed", async () => {
    render(<Toaster />);
    act(() => {
      toast.info("Message sent");
    });

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));

    await waitFor(() =>
      expect(screen.queryByText("Message sent")).not.toBeInTheDocument(),
    );
  });
});

describe("confirm dialog", () => {
  it("asks first, then passes the form fields to the action", async () => {
    const onConfirm = vi.fn().mockResolvedValue(true);
    render(
      <ConfirmDialog
        trigger={<Button>Cancel procedure</Button>}
        title="Cancel this procedure?"
        description="The slot is released for the waitlist."
        confirmLabel="Cancel procedure"
        tone="danger"
        onConfirm={onConfirm}
      >
        <input name="reason" defaultValue="NO_ESCORT" />
      </ConfirmDialog>,
    );

    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel procedure" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Cancel this procedure?",
    });
    expect(dialog).toHaveTextContent("The slot is released for the waitlist.");

    const buttons = screen.getAllByRole("button", { name: "Cancel procedure" });
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    const form = onConfirm.mock.calls[0][0] as FormData;
    expect(form.get("reason")).toBe("NO_ESCORT");
  });

  it("does nothing when the person changes their mind", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        trigger={<Button>Log call</Button>}
        title="Log a call with Asha?"
        confirmLabel="Log call"
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Log call" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onConfirm).not.toHaveBeenCalled();
  });
});
