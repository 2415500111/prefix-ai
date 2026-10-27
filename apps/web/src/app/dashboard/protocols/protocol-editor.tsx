"use client";

import {
  STEP_CATEGORIES,
  type Condition,
  type ProcedureType,
  type ProtocolInput,
  type StepCategory,
  type StepInput,
} from "@prefix/shared";
import { useId, useState, useTransition } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  CONDITION_FLAGS,
  conditionToFlags,
  flagsToCondition,
  offsetToParts,
  partsToOffset,
  type ConditionFlag,
  type OffsetUnit,
} from "@/lib/protocol-form";

import type { ActionResult } from "./actions";

interface StepDraft {
  key: string;
  title: string;
  instructionText: string;
  category: StepCategory;
  offsetValue: string;
  offsetUnit: OffsetUnit;
  requiresConfirmation: boolean;
  isCritical: boolean;
  /** null when the step uses a rule the flag picker cannot show; see customRule. */
  flags: ConditionFlag[] | null;
  customRule: string;
}

let nextKey = 0;
const newKey = () => `step-${nextKey++}`;

function toDraft(step: StepInput): StepDraft {
  const { value, unit } = offsetToParts(step.offset_minutes);
  const flags = conditionToFlags(step.conditions);
  return {
    key: newKey(),
    title: step.title,
    instructionText: step.instruction_text,
    category: step.category,
    offsetValue: String(value),
    offsetUnit: unit,
    requiresConfirmation: step.requires_confirmation,
    isCritical: step.is_critical,
    flags,
    customRule: flags === null ? JSON.stringify(step.conditions, null, 2) : "",
  };
}

function emptyDraft(): StepDraft {
  return {
    key: newKey(),
    title: "",
    instructionText: "",
    category: "DIET",
    offsetValue: "1",
    offsetUnit: "days",
    requiresConfirmation: false,
    isCritical: false,
    flags: [],
    customRule: "",
  };
}

/** Turn the form state into the API payload, or explain what is wrong. */
export function buildPayload(
  base: Omit<ProtocolInput, "steps">,
  steps: StepDraft[],
): { payload: ProtocolInput } | { error: string } {
  const built: StepInput[] = [];
  for (const [index, step] of steps.entries()) {
    const label = `Step ${index + 1}`;
    const amount = Number(step.offsetValue);
    if (!Number.isFinite(amount) || amount < 0) {
      return { error: `${label}: the timing must be zero or more.` };
    }
    let conditions: Condition | null;
    if (step.flags === null) {
      try {
        const parsed: unknown = JSON.parse(step.customRule);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          Array.isArray(parsed)
        ) {
          return { error: `${label}: the custom rule must be a JSON object.` };
        }
        conditions = parsed as Condition;
      } catch {
        return { error: `${label}: the custom rule is not valid JSON.` };
      }
    } else {
      conditions = flagsToCondition(step.flags);
    }
    built.push({
      offset_minutes: partsToOffset(amount, step.offsetUnit),
      title: step.title.trim(),
      instruction_text: step.instructionText.trim(),
      category: step.category,
      requires_confirmation: step.requiresConfirmation,
      is_critical: step.isCritical,
      conditions,
    });
  }
  return { payload: { ...base, steps: built } };
}

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function ProtocolEditor({
  protocolId,
  initial,
  procedureTypes,
  createsNewVersion,
  onSave,
}: {
  protocolId: string | null;
  initial: ProtocolInput;
  procedureTypes: ProcedureType[];
  createsNewVersion: boolean;
  onSave: (
    protocolId: string | null,
    input: ProtocolInput,
  ) => Promise<ActionResult>;
}) {
  const formId = useId();
  const [name, setName] = useState(initial.name);
  const [description, setDescription] = useState(initial.description ?? "");
  const [procedureTypeId, setProcedureTypeId] = useState(
    initial.procedure_type_id || procedureTypes[0]?.id || "",
  );
  const [steps, setSteps] = useState<StepDraft[]>(() =>
    initial.steps.map(toDraft),
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const update = (key: string, patch: Partial<StepDraft>) =>
    setSteps((current) =>
      current.map((s) => (s.key === key ? { ...s, ...patch } : s)),
    );
  const move = (index: number, delta: -1 | 1) =>
    setSteps((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target]!, next[index]!];
      return next;
    });

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = buildPayload(
      {
        procedure_type_id: procedureTypeId,
        name: name.trim(),
        description: description.trim() || null,
      },
      steps,
    );
    if ("error" in result) {
      setError(result.error);
      return;
    }
    setError(null);
    startTransition(async () => {
      const outcome = await onSave(protocolId, result.payload);
      if (outcome.error) setError(outcome.error);
    });
  };

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-6"
      aria-label="Protocol editor"
    >
      {createsNewVersion ? (
        <Alert>
          <AlertDescription>
            This version is approved and cannot change. Saving creates a new
            draft version that must be approved before it is used.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor={`${formId}-name`}>Name</Label>
          <Input
            id={`${formId}-name`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor={`${formId}-procedure`}>Procedure</Label>
          <select
            id={`${formId}-procedure`}
            className={selectClass}
            value={procedureTypeId}
            onChange={(e) => setProcedureTypeId(e.target.value)}
            required
          >
            {procedureTypes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2 sm:col-span-2">
          <Label htmlFor={`${formId}-description`}>Description</Label>
          <Textarea
            id={`${formId}-description`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={4000}
          />
        </div>
      </div>

      <section aria-label="Steps" className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Steps</h2>
        {steps.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No steps yet. A protocol needs at least one step before it can be
            approved.
          </p>
        ) : null}
        {steps.map((step, index) => {
          const id = `${formId}-${step.key}`;
          return (
            <Card
              key={step.key}
              size="sm"
              aria-label={`Step ${index + 1}`}
              role="group"
            >
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Step {index + 1}</CardTitle>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => move(index, -1)}
                    disabled={index === 0}
                  >
                    Move up
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => move(index, 1)}
                    disabled={index === steps.length - 1}
                  >
                    Move down
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={() =>
                      setSteps((current) =>
                        current.filter((s) => s.key !== step.key),
                      )
                    }
                  >
                    Remove
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-6">
                <div className="flex flex-col gap-2 sm:col-span-3">
                  <Label htmlFor={`${id}-title`}>Title</Label>
                  <Input
                    id={`${id}-title`}
                    value={step.title}
                    onChange={(e) =>
                      update(step.key, { title: e.target.value })
                    }
                    required
                    maxLength={200}
                  />
                </div>
                <div className="flex flex-col gap-2 sm:col-span-3">
                  <Label htmlFor={`${id}-category`}>Category</Label>
                  <select
                    id={`${id}-category`}
                    className={selectClass}
                    value={step.category}
                    onChange={(e) =>
                      update(step.key, {
                        category: e.target.value as StepCategory,
                      })
                    }
                  >
                    {STEP_CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c.replace("_", " ").toLowerCase()}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-2 sm:col-span-6">
                  <Label htmlFor={`${id}-instruction`}>
                    Instruction for the patient
                  </Label>
                  <Textarea
                    id={`${id}-instruction`}
                    value={step.instructionText}
                    onChange={(e) =>
                      update(step.key, { instructionText: e.target.value })
                    }
                    required
                    maxLength={2000}
                  />
                </div>
                <fieldset className="flex flex-col gap-2 sm:col-span-3">
                  <legend className="mb-2 text-sm font-medium">
                    When (before the procedure)
                  </legend>
                  <div className="flex gap-2">
                    <Input
                      aria-label="Amount"
                      type="number"
                      min={0}
                      step="any"
                      value={step.offsetValue}
                      onChange={(e) =>
                        update(step.key, { offsetValue: e.target.value })
                      }
                      className="w-24"
                      required
                    />
                    <select
                      aria-label="Unit"
                      className={selectClass}
                      value={step.offsetUnit}
                      onChange={(e) =>
                        update(step.key, {
                          offsetUnit: e.target.value as OffsetUnit,
                        })
                      }
                    >
                      <option value="minutes">minutes</option>
                      <option value="hours">hours</option>
                      <option value="days">days</option>
                    </select>
                  </div>
                </fieldset>
                <fieldset className="flex flex-col gap-2 sm:col-span-3">
                  <legend className="mb-2 text-sm font-medium">Flags</legend>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={step.isCritical}
                      onChange={(e) =>
                        update(step.key, { isCritical: e.target.checked })
                      }
                    />
                    Critical (missing it may cancel the procedure)
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={step.requiresConfirmation}
                      onChange={(e) =>
                        update(step.key, {
                          requiresConfirmation: e.target.checked,
                        })
                      }
                    />
                    Patient must confirm
                  </label>
                </fieldset>
                <fieldset className="flex flex-col gap-2 sm:col-span-6">
                  <legend className="mb-2 text-sm font-medium">
                    Applies to
                  </legend>
                  {step.flags === null ? (
                    <>
                      <Label
                        htmlFor={`${id}-rule`}
                        className="font-normal text-muted-foreground"
                      >
                        Custom rule (JSON)
                      </Label>
                      <Textarea
                        id={`${id}-rule`}
                        className="font-mono"
                        value={step.customRule}
                        onChange={(e) =>
                          update(step.key, { customRule: e.target.value })
                        }
                      />
                    </>
                  ) : (
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      <span className="text-sm text-muted-foreground">
                        {step.flags.length === 0
                          ? "All patients, or only if:"
                          : "Only if the patient:"}
                      </span>
                      {CONDITION_FLAGS.map(({ flag, label }) => (
                        <label
                          key={flag}
                          className="flex items-center gap-2 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={step.flags?.includes(flag) ?? false}
                            onChange={(e) =>
                              update(step.key, {
                                flags: e.target.checked
                                  ? [...(step.flags ?? []), flag]
                                  : (step.flags ?? []).filter(
                                      (f) => f !== flag,
                                    ),
                              })
                            }
                          />
                          {label}
                        </label>
                      ))}
                    </div>
                  )}
                </fieldset>
              </CardContent>
            </Card>
          );
        })}
        <Button
          type="button"
          variant="outline"
          onClick={() => setSteps((current) => [...current, emptyDraft()])}
          className="self-start"
        >
          Add step
        </Button>
      </section>

      {error ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex gap-2">
        <Button type="submit" size="lg" disabled={pending}>
          {pending
            ? "Saving…"
            : createsNewVersion
              ? "Save as new draft"
              : "Save draft"}
        </Button>
      </div>
    </form>
  );
}
