import { describe, expect, it } from "vitest";

import { binValues } from "./anomaly-tab";

describe("binValues", () => {
  it("counts every value once and places the claim in a bin", () => {
    const { data, claimKey } = binValues([1, 2, 3, 4, 5], 5, 4);
    expect(data.reduce((a, b) => a + b.count, 0)).toBe(5);
    expect(claimKey).toBe("b3");
  });

  it("widens the range to include an outlying claim value", () => {
    const { data, claimKey } = binValues([1, 2, 3], 30, 10);
    expect(data[data.length - 1].hi).toBe(30);
    expect(claimKey).toBe("b9");
  });

  it("handles empty and constant inputs", () => {
    expect(binValues([], 1).data).toEqual([]);
    const { data } = binValues([2, 2, 2], 2, 2);
    expect(data.reduce((a, b) => a + b.count, 0)).toBe(3);
  });
});
