"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { LoadError } from "@/components/app-shell/states";
import { AXIS_PROPS, BAR_RADIUS_H, ChartEmpty, ChartTooltip, CURSOR_FILL, GRID_PROPS } from "@/components/charts";
import { PageHeader, Panel, PanelHeader } from "@/components/page";
import { ACTION_META, isClaimAction } from "@/components/status-badges";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { DashboardSummary } from "@/lib/api/types";
import { formatDate, formatINR, formatINRCompact, formatNumber, formatPercent } from "@/lib/format";
import { humanize, num, RULE_NAMES } from "@/lib/labels";

export function Dashboard() {
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardSummary>("/api/v1/dashboard/summary"),
    refetchInterval: 60_000,
  });

  if (summary.isError) return <LoadError message={getErrorMessage(summary.error)} onRetry={() => summary.refetch()} />;
  const s = summary.data;

  return (
    <>
      <PageHeader title="Dashboard" description="Leakage identified and review workload across processed claims." />
      <Kpis s={s} />
      {s && s.kpis.processed === 0 ? (
        <Panel className="mt-4 px-4 py-10 text-center">
          <p className="text-sm font-medium">No processed claims yet</p>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Charts fill in once claims are processed. Managers can process a test batch from{" "}
            <Link href="/admin" className="font-medium text-primary hover:underline">
              Admin
            </Link>
            .
          </p>
        </Panel>
      ) : (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <ChartPanel title="Leakage by finding type" description="Rupees deducted by each rule across processed claims." loading={!s}>
            {s && <LeakageByRule rows={s.leakage_by_rule} />}
          </ChartPanel>
          <ChartPanel title="Leakage identified per week" description="By week of admission." loading={!s}>
            {s && <WeeklyLine rows={s.weekly} field="leakage" />}
          </ChartPanel>
          <ChartPanel title="Top providers by leakage" loading={!s}>
            {s && <RankedBars rows={s.leakage_by_provider.map((r) => ({ key: r.provider_id, label: r.name, value: num(r.leakage) ?? 0, claims: r.claims, href: `/providers/${encodeURIComponent(r.provider_id)}` }))} />}
          </ChartPanel>
          <ChartPanel title="Leakage by procedure" loading={!s}>
            {s && <RankedBars rows={s.leakage_by_procedure.map((r) => ({ key: r.procedure_code, label: r.name, value: num(r.leakage) ?? 0, claims: r.claims }))} />}
          </ChartPanel>
          <ChartPanel title="Auto-approval rate per week" description="Share of processed claims recommended for straight approval." loading={!s}>
            {s && <WeeklyLine rows={s.weekly} field="auto_approval_rate" />}
          </ChartPanel>
          <ChartPanel title="Recommended actions and risk tiers" loading={!s}>
            {s && <Mix s={s} />}
          </ChartPanel>
        </div>
      )}
    </>
  );
}

function Kpis({ s }: { s: DashboardSummary | undefined }) {
  const k = s?.kpis;
  const claimed = num(k?.claimed_processed) ?? 0;
  const leakage = num(k?.leakage_identified) ?? 0;
  const tiles = [
    {
      label: "Claims processed",
      value: k ? formatNumber(k.processed) : null,
      sub: k ? `of ${formatNumber(k.total_claims)} claims, ${formatNumber(k.unprocessed)} not yet processed` : null,
    },
    {
      label: "Leakage identified",
      value: k ? formatINRCompact(k.leakage_identified) : null,
      title: k ? formatINR(k.leakage_identified) : undefined,
      sub: k && claimed > 0 ? `${formatPercent(leakage / claimed)} of ${formatINRCompact(k.claimed_processed)} claimed` : null,
    },
    {
      label: "Auto-approval rate",
      value: k ? formatPercent(k.auto_approval_rate) : null,
      sub: "Recommended for straight approval",
    },
    {
      label: "Pending review",
      value: k ? formatNumber(k.pending_review) : null,
      sub: "Waiting for an adjuster",
    },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((t) => (
        <Panel key={t.label} className="px-4 py-3">
          <div className="text-xs font-medium text-muted-foreground">{t.label}</div>
          {t.value === null ? (
            <Skeleton className="mt-1.5 h-7 w-28" />
          ) : (
            <div className="mt-0.5 text-2xl leading-8 font-semibold tracking-[-0.01em]" title={t.title}>
              {t.value}
            </div>
          )}
          {t.sub && <div className="num mt-0.5 truncate text-xs text-muted-foreground">{t.sub}</div>}
        </Panel>
      ))}
    </div>
  );
}

function ChartPanel({ title, description, loading, children }: { title: string; description?: string; loading: boolean; children: React.ReactNode }) {
  return (
    <Panel className="min-w-0">
      <PanelHeader title={title} description={description} />
      <div className="px-2 py-3">{loading ? <Skeleton className="mx-2 h-64" /> : children}</div>
    </Panel>
  );
}

function LeakageByRule({ rows }: { rows: DashboardSummary["leakage_by_rule"] }) {
  const data = rows
    .map((r) => ({ code: r.rule_code, label: `${r.rule_code} ${RULE_NAMES[r.rule_code] ?? ""}`.trim(), amount: num(r.amount) ?? 0, findings: r.findings }))
    .filter((r) => r.amount > 0 || r.findings > 0);
  if (data.length === 0) return <ChartEmpty className="h-64">No rule findings yet.</ChartEmpty>;
  return (
    <div style={{ height: Math.max(160, data.length * 30 + 40) }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, bottom: 0, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
          <XAxis type="number" {...AXIS_PROPS} tickFormatter={(v: number) => formatINRCompact(v, 0)} />
          <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={210} interval={0} />
          <Tooltip
            cursor={CURSOR_FILL}
            content={(p) => (
              <ChartTooltip
                {...p}
                rows={(d) => [
                  { label: "Leakage", value: formatINR(Math.round(d.amount as number)) },
                  { label: "Findings", value: formatNumber(d.findings as number) },
                ]}
              />
            )}
          />
          <Bar
            dataKey="amount"
            fill="var(--chart-1)"
            radius={BAR_RADIUS_H}
            maxBarSize={20}
            isAnimationActive={false}
            label={{ position: "right", fill: "var(--muted-foreground)", fontSize: 11, formatter: (v: unknown) => formatINRCompact(Number(v)) }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function WeeklyLine({ rows, field }: { rows: DashboardSummary["weekly"]; field: "leakage" | "auto_approval_rate" }) {
  const data = rows.map((r) => ({ week: r.week, value: num(r[field]) ?? 0, claims: r.claims, leakage: num(r.leakage) ?? 0 }));
  if (data.length === 0) return <ChartEmpty className="h-64">No weekly data yet.</ChartEmpty>;
  const isRate = field === "auto_approval_rate";
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="week" {...AXIS_PROPS} tickFormatter={(w: string) => shortDate(w)} minTickGap={24} />
          <YAxis
            {...AXIS_PROPS}
            width={56}
            domain={isRate ? [0, 1] : [0, "auto"]}
            tickFormatter={(v: number) => (isRate ? formatPercent(v, { digits: 0 }) : formatINRCompact(v, 0))}
          />
          <Tooltip
            content={(p) => (
              <ChartTooltip
                {...p}
                formatLabel={(l) => `Week of ${formatDate(String(l))}`}
                rows={(d) => [
                  isRate
                    ? { label: "Auto-approval", value: formatPercent(d.value as number) }
                    : { label: "Leakage", value: formatINR(Math.round(d.value as number)) },
                  { label: "Claims", value: formatNumber(d.claims as number) },
                ]}
              />
            )}
          />
          <Line
            type="linear"
            dataKey="value"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--card)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function RankedBars({ rows }: { rows: { key: string; label: string; value: number; claims: number; href?: string }[] }) {
  if (rows.length === 0) return <ChartEmpty className="h-64">Nothing to rank yet.</ChartEmpty>;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ol className="space-y-1 px-2">
      {rows.map((r, i) => (
        <li key={r.key} className="grid grid-cols-[1.25rem_minmax(0,13rem)_minmax(0,1fr)_4.5rem] items-center gap-3 text-[13px]">
          <span className="num text-right text-xs text-muted-foreground">{i + 1}</span>
          <span className="truncate" title={r.label}>
            {r.href ? (
              <Link href={r.href} className="rounded-sm outline-none hover:text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring">
                {r.label}
              </Link>
            ) : (
              r.label
            )}
          </span>
          <span className="flex h-5 items-center" title={`${formatNumber(r.claims)} claims`}>
            <span className="h-3 rounded-r-[3px] bg-chart-1" style={{ width: `${Math.max(1, (r.value / max) * 100)}%` }} />
          </span>
          <span className="num text-right font-medium" title={formatINR(Math.round(r.value))}>
            {formatINRCompact(r.value)}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Mix({ s }: { s: DashboardSummary }) {
  const actions = s.by_action.map((a) => ({
    key: a.action,
    label: isClaimAction(a.action) ? ACTION_META[a.action].label : humanize(a.action),
    claims: a.claims,
    tone: isClaimAction(a.action) ? ACTION_META[a.action].tone : "--chart-4",
  }));
  const tierOrder = ["high", "medium", "low"];
  const tiers = [...s.risk_tiers].sort((a, b) => tierOrder.indexOf(a.tier) - tierOrder.indexOf(b.tier));
  const tierTotal = tiers.reduce((acc, t) => acc + t.claims, 0) || 1;
  return (
    <div className="space-y-5 px-2">
      <div className="h-44">
        <ResponsiveContainer>
          <BarChart data={actions} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 8 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="label" {...AXIS_PROPS} axisLine={false} width={150} interval={0} />
            <Tooltip
              cursor={CURSOR_FILL}
              content={(p) => <ChartTooltip {...p} rows={(d) => [{ label: "Claims", value: formatNumber(d.claims as number) }]} />}
            />
            <Bar
              dataKey="claims"
              radius={BAR_RADIUS_H}
              maxBarSize={18}
              isAnimationActive={false}
              label={{ position: "right", fill: "var(--muted-foreground)", fontSize: 11, formatter: (v: unknown) => formatNumber(Number(v)) }}
            >
              {actions.map((a) => (
                <Cell key={a.key} fill={`var(${a.tone})`} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div>
        <div className="mb-1.5 text-xs font-semibold text-muted-foreground">Risk tiers of scored claims</div>
        <div className="flex h-3 overflow-hidden rounded-[3px]" role="img" aria-label={tiers.map((t) => `${t.tier} ${t.claims}`).join(", ")}>
          {tiers.map((t, i) => (
            <span
              key={t.tier}
              className={i > 0 ? "border-l-2 border-card" : undefined}
              style={{ width: `${(t.claims / tierTotal) * 100}%`, background: `var(--risk-${t.tier}, var(--chart-4))` }}
            />
          ))}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
          {tiers.map((t) => (
            <li key={t.tier} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-[2px]" style={{ background: `var(--risk-${t.tier}, var(--chart-4))` }} aria-hidden="true" />
              <span className="text-muted-foreground">{humanize(t.tier)}</span>
              <span className="num font-medium">{formatNumber(t.claims)}</span>
              <span className="num text-muted-foreground">({formatPercent(t.claims / tierTotal, { digits: 0 })})</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}
