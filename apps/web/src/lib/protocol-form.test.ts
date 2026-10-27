import { describe, expect, it } from "vitest";

import {
  conditionToFlags,
  describeCondition,
  flagsToCondition,
  formatOffset,
  offsetToParts,
  partsToOffset,
} from "./protocol-form";

describe("offsets", () => {
  it.each([
    [7 * 24 * 60, { value: 7, unit: "days" }],
    [18 * 60, { value: 18, unit: "hours" }],
    [90, { value: 90, unit: "minutes" }],
    [0, { value: 0, unit: "minutes" }],
  ])("splits %i minutes", (minutes, parts) => {
    expect(offsetToParts(minutes)).toEqual(parts);
  });

  it("round-trips through parts", () => {
    for (const minutes of [0, 30, 60, 300, 1440, 4320, 10080]) {
      const { value, unit } = offsetToParts(minutes);
      expect(partsToOffset(value, unit)).toBe(minutes);
    }
  });

  it("converts fractional input to whole minutes", () => {
    expect(partsToOffset(1.5, "hours")).toBe(90);
  });

  it("formats for people", () => {
    expect(formatOffset(0)).toBe("At the procedure");
    expect(formatOffset(1440)).toBe("1 day before");
    expect(formatOffset(3 * 1440)).toBe("3 days before");
    expect(formatOffset(120)).toBe("2 hours before");
  });
});

describe("conditions", () => {
  it("maps no condition to no flags", () => {
    expect(conditionToFlags(null)).toEqual([]);
    expect(flagsToCondition([])).toBeNull();
  });

  it("round-trips single and multiple flags", () => {
    const one = flagsToCondition(["on_anticoagulant"]);
    const two = flagsToCondition(["on_anticoagulant", "diabetic_on_insulin"]);

    expect(one).toEqual({ flag: "on_anticoagulant" });
    expect(two).toEqual({
      any: [{ flag: "on_anticoagulant" }, { flag: "diabetic_on_insulin" }],
    });
    expect(conditionToFlags(one)).toEqual(["on_anticoagulant"]);
    expect(conditionToFlags(two)).toEqual([
      "on_anticoagulant",
      "diabetic_on_insulin",
    ]);
  });

  it("treats anything else as a custom rule", () => {
    const egfr = {
      any: [
        { missing: "egfr_value" },
        { compare: { field: "egfr_value", op: "lt", value: 45 } },
      ],
    };
    expect(conditionToFlags(egfr)).toBeNull();
    expect(conditionToFlags({ flag: "unknown_flag" })).toBeNull();
    expect(conditionToFlags({ not: { flag: "on_anticoagulant" } })).toBeNull();
    expect(describeCondition(egfr)).toBe("Custom rule");
  });

  it("describes conditions in plain words", () => {
    expect(describeCondition(null)).toBe("All patients");
    expect(describeCondition({ flag: "has_metal_implant" })).toBe(
      "Only if: metal implant or device",
    );
  });
});
