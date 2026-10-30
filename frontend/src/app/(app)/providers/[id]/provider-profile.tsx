"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ListFilter } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { LoadError } from "@/components/app-shell/states";
import { AXIS_PROPS, ChartEmpty, ChartTooltip, GRID_PROPS, LegendKey } from "@/components/charts";
import { Panel, PanelHeader } from "@/components/page";
import { ToneBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { ProviderProfile as Profile } from "@/lib/api/types";
import { formatDate, formatINR, formatINRCompact, formatNumber, formatPercent } from "@/lib/format";
import { num } from "@/lib/labels";

import { OE_ALERT, OeValue } from "../providers-table";

export function ProviderProfile() {
  const { id: raw } = useParams<{ id: string }>();
  const id = decodeURIComponent(raw);
  const q = useQuery({
    queryKey: ["provider", id],
    queryFn: () => apiRequest<Profile>(`/api/v1/providers/${encodeURIComponent(id)}`),
  });

  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404) {
      return <p className="py-20 text-center text-sm">Provider {id} was not found.</p>;
    }
    return <LoadError message={getErrorMessage(q.error)} onRetry={() => q.refetch()} />;
  }
  const d = q.data;
  const p = d?.provider;
  const s = d?.summary;

  return (
    <>
      <Link
        href="/providers"
        className="-ml-1 mb-2 inline-flex items-center gap-0.5 rounded-sm px-1 text-[13px] font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="size-3.5" aria-hidden="true" />
        Providers
      </Link>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {p ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl leading-7 font-semibold tracking-[-0.01em]">{p.name}</h1>
                {p.nabh && <ToneBadge tone="--action-approve">NABH</ToneBadge>}
                <ToneBadge className="font-medium">{p.network ? "Network" : "Non-network"}</ToneBadge>
              </div>
              <p className="mt-1 text-[13px] text-muted-foreground">
                <span className="num">{p.id}</span>, {p.city}, hospital tier {p.hospital_tier}, city tier {p.city_tier}
                {p.beds ? `, ${formatNumber(p.beds)} beds` : ""}
                {p.joined_at ? `, joined ${formatDate(p.joined_at)}` : ""}
              </p>
            </>
          ) : (
            <>
              <Skeleton className="h-7 w-72" />
              <Skeleton className="mt-2 h-4 w-96 max-w-full" />
            </>
          )}
        </div>
        <Button asChild variant="outline" className="bg-card">
          <Link href={`/claims?provider_id=${encodeURIComponent(id)}&split=`}>
            <ListFilter data-icon="inline-start" aria-hidden="true" />
            View claims
          </Link>
        </Button>
      </div>

      <Panel className="mb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
        <Stat label="Claims" value={s ? formatNumber(s.claims) : undefined} />
        <Stat label="Claimed" value={s ? formatINRCompact(s.claimed_total) : undefined} title={s ? formatINR(s.claimed_total) : undefined} />
        <Stat label="Leakage" value={s ? formatINRCompact(s.leakage_total) : undefined} title={s ? formatINR(s.leakage_total) : undefined} />
        <Stat label="Flag rate" value={s ? formatPercent(s.flag_rate) : undefined} />
        <div className="px-4 py-3">
          <div className="text-xs font-medium text-muted-foreground">O/E index</div>
          <div className="mt-1">{s ? <OeValue value={num(s.oe_index)} /> : d ? "–" : <Skeleton className="h-5 w-12" />}</div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel className="min-w-0">
          <PanelHeader title="Billing against expectation over time" description="Observed over expected claimed amount, per period. 1.0 bills like peers." />
          <div className="px-2 py-3">
            {!d ? <Skeleton className="mx-2 h-64" /> : <OeTrend trend={d.trend} />}
          </div>
        </Panel>
        <Panel className="min-w-0">
          <PanelHeader title="Common findings" />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rule</TableHead>
                <TableHead className="text-right">Findings</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d?.common_findings.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={3} className="py-6 text-center text-muted-foreground">
                    No rule findings for this provider.
                  </TableCell>
                </TableRow>
              )}
              {d?.common_findings.map((f) => (
                <TableRow key={f.rule_code}>
                  <TableCell>
                    <span className="num mr-1.5 text-muted-foreground">{f.rule_code}</span>
                    {f.rule_name}
                  </TableCell>
                  <TableCell className="num text-right">{formatNumber(f.findings)}</TableCell>
                  <TableCell className="num text-right">{formatINR(f.amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
        <Panel className="min-w-0 xl:col-span-2">
          <PanelHeader title="Top procedures" />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Procedure</TableHead>
                <TableHead className="text-right">Claims</TableHead>
                <TableHead className="text-right">Average claimed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d?.top_procedures.map((r) => (
                <TableRow key={r.procedure_code}>
                  <TableCell>
                    {r.name} <span className="num text-xs text-muted-foreground">{r.procedure_code}</span>
                  </TableCell>
                  <TableCell className="num text-right">{formatNumber(r.claims)}</TableCell>
                  <TableCell className="num text-right">{formatINR(Math.round(num(r.avg_claimed) ?? 0))}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      </div>
    </>
  );
}

function Stat({ label, value, title }: { label: string; value?: string; title?: string }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      {value === undefined ? (
        <Skeleton className="mt-1.5 h-5 w-20" />
      ) : (
        <div className="num mt-0.5 truncate text-lg leading-7 font-semibold" title={title}>
          {value}
        </div>
      )}
    </div>
  );
}

function OeTrend({ trend }: { trend: Profile["trend"] }) {
  const data = trend.map((t) => ({ ...t, oe: num(t.oe_index) }));
  if (data.length === 0) return <ChartEmpty className="h-64">No periods computed yet.</ChartEmpty>;
  const max = Math.max(...data.map((d) => d.oe ?? 0), OE_ALERT + 0.1);
  return (
    <>
      <LegendKey
        className="mb-1 px-2"
        items={[
          { label: "Peers (1.0)", color: "var(--chart-axis)", dashed: true },
          { label: `Alert (${OE_ALERT})`, color: "var(--risk-high)", dashed: true },
        ]}
      />
      <div className="h-64">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="period" {...AXIS_PROPS} minTickGap={20} tickFormatter={(p: string) => formatPeriod(p)} />
            <YAxis {...AXIS_PROPS} width={40} domain={[0, Math.ceil(max * 10) / 10]} tickFormatter={(v: number) => v.toFixed(1)} />
            <ReferenceLine y={1} stroke="var(--chart-axis)" strokeDasharray="4 3" strokeWidth={1.5} />
            <ReferenceLine y={OE_ALERT} stroke="var(--risk-high)" strokeDasharray="4 3" strokeWidth={1.5} />
            <Tooltip
              content={(p) => (
                <ChartTooltip
                  {...p}
                  formatLabel={(l) => formatPeriod(String(l), true)}
                  rows={(r) => [
                    { label: "O/E index", value: r.oe === null ? "–" : (r.oe as number).toFixed(2) },
                    { label: "Claims", value: formatNumber(r.claims as number) },
                    { label: "Leakage", value: formatINR(r.leakage_total as string) },
                    { label: "Flag rate", value: formatPercent(r.flag_rate as number) },
                  ]}
                />
              )}
            />
            <Line
              type="linear"
              dataKey="oe"
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--chart-1)", stroke: "var(--card)", strokeWidth: 2 }}
              activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
              isAnimationActive={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function formatPeriod(period: string, long = false): string {
  const d = new Date(`${period.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return period;
  return d.toLocaleDateString("en-IN", { month: long ? "long" : "short", year: long ? "numeric" : "2-digit", timeZone: "UTC" });
}
