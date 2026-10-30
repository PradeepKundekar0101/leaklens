import { describe, expect, it } from "vitest";

import { findQuote } from "./clause-dialog";

describe("findQuote", () => {
  const text = "4.2 Room rent.\nRoom rent and boarding expenses are payable up to  2% of the Sum Insured per day.";

  it("matches across differing whitespace and case", () => {
    const range = findQuote(text, "room rent and boarding expenses are payable up to 2% of the sum insured");
    expect(range).not.toBeNull();
    expect(text.slice(...range!)).toBe("Room rent and boarding expenses are payable up to  2% of the Sum Insured");
  });

  it("returns null when the quote is absent or empty", () => {
    expect(findQuote(text, "ICU charges are payable")).toBeNull();
    expect(findQuote(text, "  ")).toBeNull();
    expect(findQuote(text, null)).toBeNull();
  });

  it("treats regex characters literally", () => {
    expect(findQuote("Cap (2%) applies.", "Cap (2%)")).toEqual([0, 8]);
  });
});
