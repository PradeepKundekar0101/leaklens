import Link from "next/link";

import { Panel, PanelHeader } from "@/components/page";
import { ToneBadge } from "@/components/status-badges";
import type { ClaimDetail, PayableStep } from "@/lib/api/types";
import { formatEvidence } from "@/lib/evidence";
import { formatINR } from "@/lib/format";
import { humanize, SEVERITY_TONE } from "@/lib/labels";

export function RulesTab({ claim }: { claim: ClaimDetail }) {
  const steps = (claim.recommendation?.payable_steps ?? []) as unknown as PayableStep[];
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          title="Rule findings"
          description="Deterministic checks against the policy, tariffs and item reference prices."
        />
        {claim.rule_findings.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">
            {claim.recommendation ? "No rule fired on this claim." : "Rules run when the claim is processed."}
          </p>
        ) : (
          <ul className="divide-y">
            {claim.rule_findings.map((f) => {
              const { facts, lists } = formatEvidence(f.evidence);
              const duplicates = Array.isArray(f.evidence.duplicate_of) ? (f.evidence.duplicate_of as string[]) : [];
              return (
                <li key={f.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <ToneBadge tone={SEVERITY_TONE[f.severity] ?? "--risk-medium"}>
                        <span className="num">{f.rule_code}</span>
                      </ToneBadge>
                      <span className="text-[13px] font-semibold">{f.rule_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {humanize(f.severity)} severity
                        {f.clause_ref && `, clause ${f.clause_ref}`}
                        {f.line_item_id !== null && `, line ${lineLabel(claim, f.line_item_id)}`}
                      </span>
                    </div>
                    <span className="num text-[13px] font-semibold text-leakage">
                      {Number(f.amount_impact) > 0 ? `−${formatINR(f.amount_impact)}` : formatINR(f.amount_impact)}
                    </span>
                  </div>
                  {facts.length > 0 && (
                    <dl className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-x-4 gap-y-1.5 text-xs">
                      {facts.map((fact) => (
                        <div key={fact.key} className="min-w-0">
                          <dt className="text-muted-foreground">{fact.label}</dt>
                          <dd className="num truncate font-medium" title={fact.value}>
                            {fact.key === "duplicate_of"
                              ? duplicates.map((id, i) => (
                                  <span key={id}>
                                    {i > 0 && ", "}
                                    <Link href={`/claims/${encodeURIComponent(id)}`} className="text-primary hover:underline">
                                      {id}
                                    </Link>
                                  </span>
                                ))
                              : fact.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  {lists.map((list) => (
                    <div key={list.key} className="mt-2.5">
                      <div className="mb-1 text-xs text-muted-foreground">{list.label}</div>
                      <table className="text-xs">
                        <tbody>
                          {list.rows.map((r, i) => (
                            <tr key={i}>
                              <td className="py-0.5 pr-6 font-medium">{r.label}</td>
                              <td className="num py-0.5 pr-4 text-right">{r.amount}</td>
                              {r.deduction !== null && (
                                <td className="num py-0.5 text-right text-leakage">
                                  <span className="mr-1.5 text-muted-foreground" aria-hidden="true">
                                    →
                                  </span>
                                  <span className="sr-only">deduction </span>−{r.deduction}
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <Panel>
        <PanelHeader title="Payable calculation" description="Each step applied in order to the claimed amount." />
        {steps.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">
            {claim.recommendation ? "No deductions: the payable equals the claimed amount." : "Calculated when the claim is processed."}
          </p>
        ) : (
          <Waterfall steps={steps} claimed={claim.recommendation?.claimed_amount ?? claim.claimed_amount} payable={claim.recommendation?.payable_amount} />
        )}
      </Panel>
    </div>
  );
}

function Waterfall({ steps, claimed, payable }: { steps: PayableStep[]; claimed: string; payable?: string }) {
  const max = Math.max(Number(claimed), ...steps.map((s) => Number(s.before)), 1);
  const pct = (v: string | number) => `${Math.max(0, Math.min(100, (Number(v) / max) * 100))}%`;
  return (
    <div className="px-4 py-3">
      <table className="w-full text-[13px]">
        <thead className="sr-only">
          <tr>
            <th>Step</th>
            <th>Bar</th>
            <th>Change</th>
            <th>After</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="py-1.5 pr-3 font-medium whitespace-nowrap">Claimed</td>
            <td className="w-full py-1.5 pr-3">
              <div className="h-3 rounded-r-[3px] bg-chart-4/40" style={{ width: pct(claimed) }} />
            </td>
            <td className="py-1.5 pr-3" />
            <td className="num py-1.5 text-right font-semibold whitespace-nowrap">{formatINR(claimed)}</td>
          </tr>
          {steps.map((s) => {
            const delta = Number(s.delta);
            return (
              <tr key={`${s.step}-${s.name}`} className="border-t border-dashed">
                <td className="py-1.5 pr-3 align-top">
                  <div className="font-medium whitespace-nowrap">
                    {s.step > 0 && <span className="num mr-1.5 text-muted-foreground">{s.step}</span>}
                    {s.name}
                  </div>
                  {s.detail && <div className="max-w-64 text-xs text-muted-foreground">{s.detail}</div>}
                </td>
                <td className="py-1.5 pr-3 align-top">
                  <div className="relative mt-1 h-3">
                    <div className="absolute inset-y-0 left-0 rounded-r-[3px] bg-chart-1" style={{ width: pct(s.after) }} />
                    {delta > 0 && (
                      <div
                        className="absolute inset-y-0 rounded-r-[3px] bg-leakage/70"
                        style={{ left: `calc(${pct(s.after)} + 2px)`, width: `calc(${pct(delta)} - 2px)` }}
                        title={`${formatINR(s.delta)} deducted`}
                      />
                    )}
                  </div>
                </td>
                <td className="num py-1.5 pr-3 text-right align-top whitespace-nowrap text-leakage">
                  {delta !== 0 ? `−${formatINR(s.delta)}` : ""}
                </td>
                <td className="num py-1.5 text-right align-top whitespace-nowrap">{formatINR(s.after)}</td>
              </tr>
            );
          })}
          {payable && (
            <tr className="border-t">
              <td className="pt-2 pr-3 font-semibold">Payable</td>
              <td />
              <td />
              <td className="num pt-2 text-right font-semibold whitespace-nowrap">{formatINR(payable)}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function lineLabel(claim: ClaimDetail, id: number): string {
  const li = claim.line_items.find((l) => l.id === id);
  return li ? li.description : `#${id}`;
}
