"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AXIS_PROPS, BAR_RADIUS_H, BAR_RADIUS_V, ChartEmpty, ChartTooltip, CURSOR_FILL, GRID_PROPS, LegendKey } from "@/components/charts";
import { Panel, PanelHeader } from "@/components/page";
import { isRiskLevel, RiskBadge } from "@/components/status-badges";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { AnomalyReason, ClaimDetail, FeatureZ, PeerDistribution, ShapContributor } from "@/lib/api/types";
import { formatNumber, formatPercent } from "@/lib/format";
import { featureLabel, formatFeatureValue, PEER_FEATURES, type PeerFeature } from "@/lib/labels";

const Z_MEDIUM = 2.5;
const Z_HIGH = 3.5;
/** Peer group levels from backend/app/services/anomaly/peer_stats.py LEVEL_KEYS. */
const LEVEL_LABELS: Record<number, string> = {
  1: "same procedure, hospital tier and city tier",
  2: "same procedure and hospital tier",
  3: "same procedure",
};

export function AnomalyTab({ claim }: { claim: ClaimDetail }) {
  const a = claim.anomaly;
  const featureZ = useMemo(() => (a?.feature_z ?? {}) as Record<string, FeatureZ>, [a]);
  const topFeature = useMemo(() => {
    const entries = Object.entries(featureZ).sort((x, y) => y[1].one_sided - x[1].one_sided);
    const f = entries[0]?.[0];
    return (PEER_FEATURES as readonly string[]).includes(f ?? "") ? (f as PeerFeature) : "log_amount";
  }, [featureZ]);
  const [feature, setFeature] = useState<PeerFeature | null>(null);
  const selected = feature ?? topFeature;

  if (!a) {
    return (
      <Panel className="px-4 py-10 text-center">
        <p className="text-sm font-medium">No anomaly score yet</p>
        <p className="mt-0.5 text-[13px] text-muted-foreground">The claim is scored against its peers when it is processed.</p>
      </Panel>
    );
  }

  const zData = Object.entries(featureZ)
    .map(([f, d]) => ({ feature: f, label: featureLabel(f), z: d.one_sided, rz: d.rz, value: d.value, median: d.median, n: d.n }))
    .sort((x, y) => y.z - x.z);
  const shap = a.shap as unknown as ShapContributor[];
  const reasons = a.reasons as unknown as AnomalyReason[];

  return (
    <div className="space-y-4">
      <Panel className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
        <Fact label="Tier">{isRiskLevel(a.tier) ? <RiskBadge level={a.tier} /> : a.tier}</Fact>
        <Fact label="Risk score">{a.risk.toFixed(3)}</Fact>
        <Fact label="Peer z (p_z)" hint="Probability-like score from the robust z of each feature against peers">
          {a.p_z.toFixed(3)}
        </Fact>
        <Fact label="Isolation forest (p_if)" hint="Unusualness of the combination of features">
          {a.p_if.toFixed(3)}
        </Fact>
        <Fact label="Max robust z">{a.max_rz.toFixed(2)}</Fact>
        <Fact label="Model" hint={a.model_version}>{a.model_version}</Fact>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader
            title="How unusual each feature is"
            description="One-sided robust z against the claim's peer group. Only the costly direction counts."
          />
          <div className="px-2 pt-3 pb-2">
            <LegendKey
              className="mb-1 px-2"
              items={[
                { label: `Review line (${Z_MEDIUM})`, color: "var(--risk-medium)", dashed: true },
                { label: `Strong signal (${Z_HIGH})`, color: "var(--risk-high)", dashed: true },
              ]}
            />
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={zData} layout="vertical" margin={{ top: 8, right: 24, bottom: 0, left: 8 }}>
                  <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
                  <XAxis type="number" {...AXIS_PROPS} domain={[0, (max: number) => niceMax(max)]} allowDecimals={false} />
                  <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={150} interval={0} />
                  <Tooltip
                    cursor={CURSOR_FILL}
                    content={(p) => (
                      <ChartTooltip
                        {...p}
                        rows={(d) => [
                          { label: "One-sided z", value: Number(d.z).toFixed(2) },
                          { label: "This claim", value: formatFeatureValue(String(d.feature), d.value as number) },
                          { label: "Peer median", value: formatFeatureValue(String(d.feature), d.median as number | null) },
                          { label: "Peers", value: formatNumber(d.n as number) },
                        ]}
                      />
                    )}
                  />
                  <ReferenceLine x={Z_MEDIUM} stroke="var(--risk-medium)" strokeDasharray="4 3" strokeWidth={1.5} />
                  <ReferenceLine x={Z_HIGH} stroke="var(--risk-high)" strokeDasharray="4 3" strokeWidth={1.5} />
                  <Bar dataKey="z" radius={BAR_RADIUS_H} maxBarSize={18} isAnimationActive={false}>
                    {zData.map((d) => (
                      <Cell
                        key={d.feature}
                        fill={d.z >= Z_HIGH ? "var(--risk-high)" : d.z >= Z_MEDIUM ? "var(--risk-medium)" : "var(--chart-4)"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Why it was flagged" />
          <div className="space-y-4 px-4 py-3">
            {reasons.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">No feature is unusual enough to explain on its own.</p>
            ) : (
              <ul className="space-y-1.5 text-[13px]">
                {reasons.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground/60" aria-hidden="true" />
                    <span>
                      {r.text}
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {r.source === "robust_z" ? "peer comparison" : "isolation forest"}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div>
              <h3 className="mb-1.5 text-xs font-semibold text-muted-foreground">Top contributors to the isolation forest score</h3>
              {shap.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">No feature pushes this claim towards unusual.</p>
              ) : (
                <ShapBars items={shap} />
              )}
            </div>
          </div>
        </Panel>
      </div>

      <PeerHistogram claimId={claim.id} feature={selected} onFeature={setFeature} />
    </div>
  );
}

function Fact({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 px-4 py-3" title={hint}>
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="num mt-1 truncate text-[15px] font-semibold">{children}</div>
    </div>
  );
}

function ShapBars({ items }: { items: ShapContributor[] }) {
  const max = Math.max(...items.map((i) => Math.abs(i.shap)), 0.0001);
  return (
    <ul className="space-y-2">
      {items.map((i) => (
        <li key={i.feature} className="grid grid-cols-[12.5rem_minmax(0,1fr)_3.5rem] items-center gap-3 text-[13px]">
          <span className="truncate">
            {i.label}
            <span className="ml-1.5 text-xs text-muted-foreground">{i.display_value}</span>
          </span>
          <span className="h-2.5 rounded-r-[3px] bg-chart-1" style={{ width: `${(Math.abs(i.shap) / max) * 100}%` }} />
          <span className="num text-right text-xs text-muted-foreground">{i.shap.toFixed(3)}</span>
        </li>
      ))}
    </ul>
  );
}

const BINS = 28;

function PeerHistogram({
  claimId,
  feature,
  onFeature,
}: {
  claimId: string;
  feature: PeerFeature;
  onFeature: (f: PeerFeature) => void;
}) {
  const dist = useQuery({
    queryKey: ["peer-distribution", claimId, feature],
    queryFn: () =>
      apiRequest<PeerDistribution>(`/api/v1/claims/${encodeURIComponent(claimId)}/peer-distribution`, { query: { feature } }),
    staleTime: 10 * 60_000,
  });

  const bins = useMemo(() => (dist.data ? binValues(dist.data.values, dist.data.claim_value) : null), [dist.data]);
  const d = dist.data;

  return (
    <Panel>
      <PanelHeader
        title="Peer distribution"
        description={
          d
            ? `${formatNumber(d.n)} training claims, ${LEVEL_LABELS[d.level] ?? `level ${d.level}`}. The marker shows this claim.`
            : "Where this claim sits among similar training claims."
        }
        actions={
          <Select value={feature} onValueChange={(v) => onFeature(v as PeerFeature)}>
            <SelectTrigger size="sm" className="w-48 bg-card text-[13px]" aria-label="Feature">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PEER_FEATURES.map((f) => (
                <SelectItem key={f} value={f}>
                  {featureLabel(f)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />
      <div className="grid gap-4 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="h-60 min-w-0">
          {dist.isPending ? (
            <Skeleton className="h-full w-full" />
          ) : dist.isError ? (
            <ChartEmpty>{getErrorMessage(dist.error)}</ChartEmpty>
          ) : !bins || bins.data.length === 0 ? (
            <ChartEmpty>No peer claims to compare with.</ChartEmpty>
          ) : (
            <ResponsiveContainer>
              <BarChart data={bins.data} margin={{ top: 18, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis
                  dataKey="key"
                  {...AXIS_PROPS}
                  tickFormatter={(key: string) => formatFeatureValue(feature, bins.data.find((b) => b.key === key)?.mid, true)}
                  interval={Math.ceil(BINS / 6) - 1}
                  minTickGap={8}
                />
                <YAxis {...AXIS_PROPS} width={36} allowDecimals={false} />
                <Tooltip
                  cursor={CURSOR_FILL}
                  content={(p) => (
                    <ChartTooltip
                      {...p}
                      formatLabel={() => null}
                      rows={(row) => [
                        {
                          label: "Range",
                          value: `${formatFeatureValue(feature, row.lo as number, true)} to ${formatFeatureValue(feature, row.hi as number, true)}`,
                        },
                        { label: "Peer claims", value: formatNumber(row.count as number) },
                      ]}
                    />
                  )}
                />
                <Bar dataKey="count" radius={BAR_RADIUS_V} isAnimationActive={false}>
                  {bins.data.map((b) => (
                    <Cell key={b.key} fill={b.key === bins.claimKey ? "var(--leakage)" : "var(--chart-1)"} fillOpacity={b.key === bins.claimKey ? 1 : 0.55} />
                  ))}
                </Bar>
                <ReferenceLine
                  x={bins.claimKey}
                  stroke="var(--leakage)"
                  strokeWidth={2}
                  label={{
                    value: "This claim",
                    position: Number(bins.claimKey.slice(1)) > BINS * 0.6 ? "insideTopRight" : "insideTopLeft",
                    fill: "var(--foreground)",
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        {d && (
          <dl className="grid grid-cols-2 content-start gap-x-4 gap-y-2 text-[13px] lg:grid-cols-1">
            <Q label="This claim" value={formatFeatureValue(feature, d.claim_value)} strong />
            <Q label="Percentile" value={d.percentile === null ? "–" : formatPercent(d.percentile, { digits: 0 })} strong />
            <Q label="Median (p50)" value={formatFeatureValue(feature, d.quantiles.p50)} />
            <Q label="p90" value={formatFeatureValue(feature, d.quantiles.p90)} />
            <Q label="p99" value={formatFeatureValue(feature, d.quantiles.p99)} />
          </dl>
        )}
      </div>
    </Panel>
  );
}

function Q({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 lg:border-b lg:border-dashed lg:pb-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={strong ? "num font-semibold" : "num"}>{value}</dd>
    </div>
  );
}

/** Equal-width bins over the peer values, widened to include the claim's own value. */
export function binValues(values: number[], claimValue: number, bins = BINS) {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) return { data: [] as { key: string; lo: number; hi: number; mid: number; count: number }[], claimKey: "" };
  let lo = Math.min(...finite, claimValue);
  let hi = Math.max(...finite, claimValue);
  if (lo === hi) {
    lo -= 0.5;
    hi += 0.5;
  }
  const width = (hi - lo) / bins;
  const data = Array.from({ length: bins }, (_, i) => ({
    key: `b${i}`,
    lo: lo + i * width,
    hi: lo + (i + 1) * width,
    mid: lo + (i + 0.5) * width,
    count: 0,
  }));
  const idx = (v: number) => Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / width)));
  for (const v of finite) data[idx(v)].count += 1;
  return { data, claimKey: `b${idx(claimValue)}` };
}

function niceMax(max: number): number {
  const target = Math.max(4, max + 0.5);
  const step = target <= 10 ? 1 : target <= 25 ? 5 : 10;
  return Math.ceil(target / step) * step;
}
