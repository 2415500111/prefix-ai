import type { AssistantReply } from "@prefix/shared";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssistantPanel } from "./assistant-panel";

const ANSWER: AssistantReply = {
  id: "11111111-1111-4111-8111-111111111111",
  question: "When do I start the diet?",
  reply: "Start the low-fibre diet 3 days before.",
  outcome: "ANSWERED",
  escalated: false,
  citations: [
    {
      event_id: "22222222-2222-4222-8222-222222222222",
      title: "Low-fibre diet",
    },
  ],
  created_at: "2026-10-28T06:00:00Z",
};

const EMERGENCY: AssistantReply = {
  ...ANSWER,
  id: "33333333-3333-4333-8333-333333333333",
  question: "I have chest pain",
  reply: "Please call 112 now.",
  outcome: "RED_FLAG",
  escalated: true,
  citations: [],
};

const askAssistant = vi.fn();

vi.mock("../actions", () => ({
  askAssistant: (...args: unknown[]) => askAssistant(...args),
}));

describe("assistant panel", () => {
  it("links each cited step to its place in the timeline", () => {
    render(
      <AssistantPanel
        appointmentId="44444444-4444-4444-8444-444444444444"
        lang="en"
        history={[ANSWER]}
      />,
    );

    // The latest reply is shown in full only once asked; earlier ones sit in the history.
    fireEvent.click(screen.getByText(/Earlier questions/));
    const link = screen.getByRole("link", { name: "Low-fibre diet" });
    expect(link).toHaveAttribute(
      "href",
      "/p/prep#step-22222222-2222-4222-8222-222222222222",
    );
  });

  it("explains that answers come only from the plan", () => {
    render(
      <AssistantPanel
        appointmentId="44444444-4444-4444-8444-444444444444"
        lang="en"
        history={[]}
      />,
    );

    expect(
      screen.getByText(
        "Answers come only from your prep plan. For anything else, your care team answers.",
      ),
    ).toBeInTheDocument();
  });

  it("announces an emergency reply at once, as an alert", async () => {
    askAssistant.mockResolvedValue({ reply: EMERGENCY, error: null });
    render(
      <AssistantPanel
        appointmentId="44444444-4444-4444-8444-444444444444"
        lang="en"
        history={[]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: "I have chest pain" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send question" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Please call 112 now.",
      ),
    );
  });
});
