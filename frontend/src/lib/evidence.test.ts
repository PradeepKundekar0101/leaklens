import { describe, expect, it } from "vitest";

import { evidenceLabel, formatEvidence, formatEvidenceValue } from "./evidence";

describe("formatEvidenceValue", () => {
  it.each([
    ["sum_insured", "300000.00", "₹3,00,000"],
    ["proportional_deduction", "7451.65", "₹7,451.65"],
    ["room_rent_per_day", "32900.00", "₹32,900"],
    ["cap_per_day", "20000.00", "₹20,000"],
    ["package_rate", "188000.00", "₹1,88,000"],
    ["claimed_amount", "1200.5", "₹1,200.50"],
    ["cap_pct_of_si", "1.000", "1% of SI"],
    ["copay_pct", "10.00", "10%"],
    ["days", "1.00", "1 day"],
    ["days", "7.00", "7 days"],
    ["qty", "3.00", "3"],
    ["ratio", "0.8451", "84.5%"],
    ["admission_at", "2026-10-02", "2 Oct 2026"],
    ["service_date", "2026-10-09", "9 Oct 2026"],
    ["procedure_code", "PR_ANGIOPLASTY", "PR_ANGIOPLASTY"],
    ["duplicate_of", ["C0032031", "C0032032"], "C0032031, C0032032"],
  ])("%s %j -> %s", (key, value, expected) => {
    expect(formatEvidenceValue(key, value)).toBe(expected);
  });
});

describe("evidenceLabel", () => {
  it("uses curated labels and humanises the rest", () => {
    expect(evidenceLabel("cap_pct_of_si")).toBe("Cap % of sum insured");
    expect(evidenceLabel("room_rent_per_day")).toBe("Room rent per day");
    expect(evidenceLabel("some_new_key")).toBe("Some new key");
  });
});

describe("formatEvidence", () => {
  it("turns nested line lists into compact rows and hides line ids", () => {
    const { facts, lists } = formatEvidence({
      days: "7.00",
      associated: [{ amount: "5453.00", category: "nursing", deduction: "2138.11", line_item_id: 1 }],
      lines: [{ amount: "195700.00", category: "ot", line_item_id: 2 }],
    });
    expect(facts).toEqual([{ key: "days", label: "Days", value: "7 days" }]);
    expect(lists[0]).toEqual({
      key: "associated",
      label: "Associated charges scaled down",
      rows: [{ label: "Nursing", amount: "₹5,453", deduction: "₹2,138.11" }],
    });
    expect(lists[1].rows).toEqual([{ label: "OT", amount: "₹1,95,700", deduction: null }]);
  });
});
