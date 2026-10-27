import type { Condition } from "@prefix/shared";

/** Patient condition flags that a step can be limited to (mirrors the API whitelist). */
export const CONDITION_FLAGS = [
  { flag: "on_anticoagulant", label: "Takes a blood thinner" },
  { flag: "diabetic_on_insulin", label: "Uses insulin" },
  { flag: "on_glp1_agonist", label: "Takes a GLP-1 medicine" },
  { flag: "has_contrast_allergy", label: "Contrast allergy" },
  { flag: "has_metal_implant", label: "Metal implant or device" },
] as const;

export type ConditionFlag = (typeof CONDITION_FLAGS)[number]["flag"];

export type OffsetUnit = "minutes" | "hours" | "days";

const MINUTES_PER: Record<OffsetUnit, number> = {
  minutes: 1,
  hours: 60,
  days: 24 * 60,
};

/** Split a minute offset into the largest whole unit (days, then hours, then minutes). */
export function offsetToParts(totalMinutes: number): {
  value: number;
  unit: OffsetUnit;
} {
  if (totalMinutes > 0 && totalMinutes % MINUTES_PER.days === 0) {
    return { value: totalMinutes / MINUTES_PER.days, unit: "days" };
  }
  if (totalMinutes > 0 && totalMinutes % MINUTES_PER.hours === 0) {
    return { value: totalMinutes / MINUTES_PER.hours, unit: "hours" };
  }
  return { value: totalMinutes, unit: "minutes" };
}

export function partsToOffset(value: number, unit: OffsetUnit): number {
  return Math.round(value * MINUTES_PER[unit]);
}

/** Human label such as "3 days before" or "At the procedure". */
export function formatOffset(totalMinutes: number): string {
  if (totalMinutes === 0) return "At the procedure";
  const { value, unit } = offsetToParts(totalMinutes);
  const singular = unit.slice(0, -1);
  return `${value} ${value === 1 ? singular : unit} before`;
}

/**
 * If a condition is a simple "any of these flags" rule (or a single flag), return the flags;
 * otherwise null, meaning it must be edited as a custom JSON rule.
 */
export function conditionToFlags(
  condition: Condition | null,
): ConditionFlag[] | null {
  if (condition === null) return [];
  const known = new Set<string>(CONDITION_FLAGS.map((c) => c.flag));
  const asFlag = (node: unknown): ConditionFlag | null => {
    if (
      typeof node === "object" &&
      node !== null &&
      Object.keys(node).length === 1 &&
      "flag" in node &&
      typeof node.flag === "string" &&
      known.has(node.flag)
    ) {
      return node.flag as ConditionFlag;
    }
    return null;
  };
  const single = asFlag(condition);
  if (single) return [single];
  const children = Object.keys(condition).length === 1 ? condition.any : null;
  if (!Array.isArray(children) || children.length === 0) return null;
  const flags = children.map(asFlag);
  return flags.every((f) => f !== null) ? (flags as ConditionFlag[]) : null;
}

/** Build the rule for "applies only if the patient has any of these flags". */
export function flagsToCondition(flags: ConditionFlag[]): Condition | null {
  if (flags.length === 0) return null;
  if (flags.length === 1) return { flag: flags[0] };
  return { any: flags.map((flag) => ({ flag })) };
}

export function describeCondition(condition: Condition | null): string {
  if (condition === null) return "All patients";
  const flags = conditionToFlags(condition);
  if (flags === null) return "Custom rule";
  const labels = CONDITION_FLAGS.filter((c) => flags.includes(c.flag)).map(
    (c) => c.label.toLowerCase(),
  );
  return `Only if: ${labels.join(" or ")}`;
}
