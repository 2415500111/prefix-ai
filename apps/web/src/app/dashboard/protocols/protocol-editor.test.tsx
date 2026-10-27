import type { ProcedureType, ProtocolInput } from "@prefix/shared";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProtocolEditor } from "./protocol-editor";

const PROCEDURES: ProcedureType[] = [
  {
    id: "pt-1",
    code: "COLONOSCOPY",
    name: "Colonoscopy",
    default_duration_minutes: 45,
  },
  { id: "pt-2", code: "MRI", name: "MRI scan", default_duration_minutes: 45 },
];

const EMPTY: ProtocolInput = {
  procedure_type_id: "",
  name: "",
  description: null,
  steps: [],
};

function renderEditor(
  initial: ProtocolInput = EMPTY,
  createsNewVersion = false,
) {
  const onSave = vi.fn().mockResolvedValue({ error: null });
  render(
    <ProtocolEditor
      protocolId={initial === EMPTY ? null : "p-1"}
      initial={initial}
      procedureTypes={PROCEDURES}
      createsNewVersion={createsNewVersion}
      onSave={onSave}
    />,
  );
  return onSave;
}

function stepCard(index: number) {
  return screen.getByRole("group", { name: `Step ${index}` });
}

describe("ProtocolEditor", () => {
  it("builds a protocol with steps and sends minutes and conditions", async () => {
    const onSave = renderEditor();

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Colonoscopy prep" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    const first = within(stepCard(1));
    fireEvent.change(first.getByLabelText("Title"), {
      target: { value: "Blood thinner" },
    });
    fireEvent.change(first.getByLabelText("Instruction for the patient"), {
      target: { value: "Ask your care team." },
    });
    fireEvent.change(first.getByLabelText("Category"), {
      target: { value: "MEDICATION" },
    });
    fireEvent.change(first.getByLabelText("Amount"), {
      target: { value: "7" },
    });
    fireEvent.click(first.getByLabelText("Takes a blood thinner"));
    fireEvent.click(first.getByLabelText(/Critical/));

    const second = within(stepCard(2));
    fireEvent.change(second.getByLabelText("Title"), {
      target: { value: "Stop drinking" },
    });
    fireEvent.change(second.getByLabelText("Instruction for the patient"), {
      target: { value: "No liquids." },
    });
    fireEvent.change(second.getByLabelText("Amount"), {
      target: { value: "2" },
    });
    fireEvent.change(second.getByLabelText("Unit"), {
      target: { value: "hours" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [protocolId, payload] = onSave.mock.calls[0] as [
      string | null,
      ProtocolInput,
    ];
    expect(protocolId).toBeNull();
    expect(payload.procedure_type_id).toBe("pt-1");
    expect(payload.name).toBe("Colonoscopy prep");
    expect(payload.steps).toEqual([
      {
        offset_minutes: 7 * 24 * 60,
        title: "Blood thinner",
        instruction_text: "Ask your care team.",
        category: "MEDICATION",
        requires_confirmation: false,
        is_critical: true,
        conditions: { flag: "on_anticoagulant" },
      },
      {
        offset_minutes: 120,
        title: "Stop drinking",
        instruction_text: "No liquids.",
        category: "DIET",
        requires_confirmation: false,
        is_critical: false,
        conditions: null,
      },
    ]);
  });

  it("reorders and removes steps", () => {
    renderEditor({
      ...EMPTY,
      name: "P",
      procedure_type_id: "pt-1",
      steps: [
        {
          offset_minutes: 60,
          title: "A",
          instruction_text: "a",
          category: "DIET",
          requires_confirmation: false,
          is_critical: false,
          conditions: null,
        },
        {
          offset_minutes: 30,
          title: "B",
          instruction_text: "b",
          category: "DIET",
          requires_confirmation: false,
          is_critical: false,
          conditions: null,
        },
      ],
    });

    fireEvent.click(
      within(stepCard(2)).getByRole("button", { name: "Move up" }),
    );
    expect(within(stepCard(1)).getByLabelText("Title")).toHaveValue("B");

    fireEvent.click(
      within(stepCard(1)).getByRole("button", { name: "Remove" }),
    );
    expect(screen.getAllByRole("group", { name: /^Step \d$/ })).toHaveLength(1);
    expect(within(stepCard(1)).getByLabelText("Title")).toHaveValue("A");
  });

  it("keeps complex rules as editable JSON and rejects invalid JSON", async () => {
    const onSave = renderEditor({
      ...EMPTY,
      name: "CT",
      procedure_type_id: "pt-2",
      steps: [
        {
          offset_minutes: 4320,
          title: "Kidney test",
          instruction_text: "Arrange a test.",
          category: "LAB",
          requires_confirmation: true,
          is_critical: true,
          conditions: { any: [{ missing: "egfr_value" }] },
        },
      ],
    });

    const rule = screen.getByLabelText("Custom rule (JSON)");
    expect(rule).toHaveValue(
      JSON.stringify({ any: [{ missing: "egfr_value" }] }, null, 2),
    );

    fireEvent.change(rule, { target: { value: "{ not json" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not valid JSON",
    );
    expect(onSave).not.toHaveBeenCalled();
  });

  it("warns that saving an approved version creates a new draft", () => {
    renderEditor({ ...EMPTY, name: "P", procedure_type_id: "pt-1" }, true);

    expect(
      screen.getByText(/Saving creates a new draft version/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save as new draft" }),
    ).toBeInTheDocument();
  });

  it("shows errors returned by the server", async () => {
    const onSave = vi
      .fn()
      .mockResolvedValue({ error: "Unknown procedure type" });
    render(
      <ProtocolEditor
        protocolId={null}
        initial={{ ...EMPTY, name: "P" }}
        procedureTypes={PROCEDURES}
        createsNewVersion={false}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unknown procedure type",
    );
  });
});
