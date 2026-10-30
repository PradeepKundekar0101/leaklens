import { formatINR } from "@/lib/format";

/**
 * An illustrative hospital bill with LeakLens findings in the margin. Figures follow the
 * rules in docs/decisions.md: sum insured ₹5,00,000 with a 1% per-day room rent cap.
 */
const LINES: {
  item: string;
  detail?: string;
  amount: string;
  finding?: { rule: string; text: string; deduction: string };
}[] = [
  {
    item: "Room rent, single AC",
    detail: `4 days at ${formatINR("6500")}`,
    amount: "26000.00",
    finding: { rule: "R01", text: "Above the 1% of sum insured cap, clause 4.2", deduction: "-6000.00" },
  },
  {
    item: "Surgeon fees",
    amount: "48000.00",
    finding: { rule: "R01", text: "Proportional deduction on associated charges", deduction: "-11076.92" },
  },
  {
    item: "Inj. Ceftriaxone 1 g",
    detail: `10 at ${formatINR("180")}`,
    amount: "1800.00",
    finding: { rule: "R04", text: `Billed above the MRP of ${formatINR("62")}`, deduction: "-1180.00" },
  },
  {
    item: "Examination gloves",
    amount: "850.00",
    finding: { rule: "R05", text: "Non-payable item, annexure II", deduction: "-850.00" },
  },
  { item: "7 other lines", amount: "65350.00" },
];

export function BillExcerpt() {
  return (
    <figure className="w-full max-w-[34rem]">
      <figcaption className="mb-5">
        <p className="text-lg leading-7 font-semibold tracking-[-0.01em] text-foreground">
          Every bill line, checked against the policy before payment.
        </p>
        <p className="mt-1 max-w-[56ch] text-sm text-muted-foreground">
          LeakLens applies the policy, scores how unusual the claim is and recommends an action. An adjuster makes
          the call.
        </p>
      </figcaption>

      <div className="overflow-hidden rounded-lg border bg-card shadow-[0_1px_2px_rgb(23_32_51/0.04),0_8px_24px_-12px_rgb(23_32_51/0.12)]">
        <div className="flex items-center justify-between gap-4 border-b px-5 py-3">
          <div className="min-w-0">
            <div className="text-[13px] font-semibold">Final bill, IP/26/0187</div>
            <div className="text-xs text-muted-foreground">
              Laparoscopic cholecystectomy, sum insured {formatINR("500000")}
            </div>
          </div>
          {/* The one flourish: the recommendation, set like an ink stamp on the bill. */}
          <div
            aria-label="Recommended action: approve with deductions"
            className="shrink-0 -rotate-3 rounded-[5px] border-[1.5px] border-primary/70 px-2 py-1 text-center text-primary"
          >
            <div className="text-[10px] leading-3 font-semibold opacity-80">Recommended</div>
            <div className="text-xs leading-4 font-bold">Approve with deductions</div>
          </div>
        </div>

        <ul className="divide-y text-[13px]">
          {LINES.map((line) => (
            <li key={line.item} className="px-5 py-2.5">
              <div className="flex items-baseline justify-between gap-4">
                <span>
                  <span className="font-medium">{line.item}</span>
                  {line.detail && <span className="ml-2 text-xs text-muted-foreground">{line.detail}</span>}
                </span>
                <span className="num">{formatINR(line.amount)}</span>
              </div>
              {line.finding && (
                <div className="mt-1 flex items-baseline justify-between gap-4 text-xs">
                  <span className="flex items-baseline gap-2 text-muted-foreground">
                    <span className="num rounded-[3px] bg-primary/10 px-1 py-px font-semibold text-primary">
                      {line.finding.rule}
                    </span>
                    {line.finding.text}
                  </span>
                  <span className="num shrink-0 font-semibold text-leakage">{formatINR(line.finding.deduction)}</span>
                </div>
              )}
            </li>
          ))}
        </ul>

        <dl className="grid grid-cols-3 border-t bg-muted/50 text-[13px]">
          <Total label="Claimed" value={formatINR("142000.00")} />
          <Total label="Leakage" value={formatINR("19106.92")} className="text-leakage" />
          <Total label="Payable" value={formatINR("122893.08")} />
        </dl>
      </div>
    </figure>
  );
}

function Total({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="px-5 py-2.5 not-first:border-l">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`num mt-0.5 text-[15px] font-semibold ${className ?? ""}`}>{value}</dd>
    </div>
  );
}
