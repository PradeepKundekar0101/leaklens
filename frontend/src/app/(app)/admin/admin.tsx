"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Loader2, Play, RefreshCw } from "lucide-react";
import { useId, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { AXIS_PROPS, BAR_RADIUS_V, ChartEmpty, ChartTooltip, CURSOR_FILL, GRID_PROPS, LegendKey } from "@/components/charts";
import { JobStatusPill } from "@/components/claim-status";
import { PageHeader, Panel, PanelHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { AdminJob, ModelEntry, ModelMetrics, ScenarioMetrics } from "@/lib/api/types";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/format";
import { useJob } from "@/lib/jobs";
import { humanize } from "@/lib/labels";

const MODELS: { key: "z_only" | "iforest_only" | "combined"; label: string; color: string }[] = [
  { key: "z_only", label: "Peer z only", color: "var(--chart-1)" },
  { key: "iforest_only", label: "Isolation forest only", color: "var(--chart-2)" },
  { key: "combined", label: "Combined", color: "var(--chart-3)" },
];

export function Admin() {
  return (
    <>
      <PageHeader title="Admin" description="Batch processing, anomaly models and their evaluation." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ActionsPanel />
        <ActiveModel />
      </div>
      <div className="mt-4">
        <Evaluation />
      </div>
      <div className="mt-4">
        <JobsPanel />
      </div>
    </>
  );
}

function useStartJob(path: string, label: string) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<number | null>(null);
  const job = useJob(jobId, {
    onFinish: (j) => {
      if (j.status === "failed") toast.error(`${label} failed`, { description: j.error ?? undefined });
      else toast.success(`${label} finished`);
      void queryClient.invalidateQueries({ queryKey: ["admin"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["claims"] });
    },
  });
  const start = useMutation({
    mutationFn: (body?: unknown) => apiRequest<{ job_id: number }>(path, { method: "POST", json: body ?? {} }),
    onSuccess: (r) => {
      setJobId(r.job_id);
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
    onError: (e) => toast.error(getErrorMessage(e)),
  });
  const running = start.isPending || (jobId !== null && job.data?.status !== "done" && job.data?.status !== "failed");
  return { start, job: job.data, jobId, running };
}

function ActionsPanel() {
  const batch = useStartJob("/api/v1/admin/process-batch", "Batch processing");
  const retrain = useStartJob("/api/v1/admin/retrain", "Retraining");
  const stats = useStartJob("/api/v1/admin/provider-stats", "Provider statistics refresh");
  const [split, setSplit] = useState("test");
  const [limit, setLimit] = useState("100");
  const [concurrency, setConcurrency] = useState("5");
  const [onlyUnprocessed, setOnlyUnprocessed] = useState(true);
  const ids = { limit: useId(), conc: useId(), only: useId(), split: useId() };
  const limitN = Number(limit);
  const concN = Number(concurrency);
  const valid = Number.isInteger(limitN) && limitN >= 1 && limitN <= 5000 && Number.isInteger(concN) && concN >= 1 && concN <= 16;

  return (
    <Panel>
      <PanelHeader title="Run jobs" />
      <div className="divide-y">
        <form
          className="space-y-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) batch.start.mutate({ split, limit: limitN, concurrency: concN, only_unprocessed: onlyUnprocessed });
          }}
        >
          <div>
            <h3 className="text-[13px] font-semibold">Process a batch of claims</h3>
            <p className="text-xs text-muted-foreground">Runs the full pipeline on claims from one split.</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor={ids.split}>Split</Label>
              <Select value={split} onValueChange={setSplit}>
                <SelectTrigger id={ids.split} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="test">Test</SelectItem>
                  <SelectItem value="train">Train</SelectItem>
                  <SelectItem value="live">Live</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.limit}>Claims (max 5,000)</Label>
              <Input id={ids.limit} type="number" min={1} max={5000} value={limit} onChange={(e) => setLimit(e.target.value)} className="num" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.conc}>Concurrency (1 to 16)</Label>
              <Input id={ids.conc} type="number" min={1} max={16} value={concurrency} onChange={(e) => setConcurrency(e.target.value)} className="num" />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label htmlFor={ids.only} className="flex items-center gap-2 text-[13px]">
              <Checkbox id={ids.only} checked={onlyUnprocessed} onCheckedChange={(v) => setOnlyUnprocessed(v === true)} />
              Only claims not yet processed
            </label>
            <div className="flex items-center gap-3">
              <JobInline job={batch.job} jobId={batch.jobId} />
              <Button type="submit" disabled={!valid || batch.running}>
                {batch.running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play data-icon="inline-start" aria-hidden="true" />}
                Process batch
              </Button>
            </div>
          </div>
        </form>

        <ActionRow
          title="Retrain anomaly models"
          description="Refits peer statistics and the isolation forest on the training split, then evaluates on test."
          button="Retrain"
          icon={<BarChart3 data-icon="inline-start" aria-hidden="true" />}
          state={retrain}
          onRun={() => retrain.start.mutate(undefined)}
        />
        <ActionRow
          title="Refresh provider statistics"
          description="Recomputes O/E indices, flag rates and leakage per provider and period."
          button="Refresh"
          icon={<RefreshCw data-icon="inline-start" aria-hidden="true" />}
          state={stats}
          onRun={() => stats.start.mutate(undefined)}
        />
      </div>
    </Panel>
  );
}

function ActionRow({
  title,
  description,
  button,
  icon,
  state,
  onRun,
}: {
  title: string;
  description: string;
  button: string;
  icon: React.ReactNode;
  state: ReturnType<typeof useStartJob>;
  onRun: () => void;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3">
      <div className="min-w-0">
        <h3 className="text-[13px] font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="flex items-center gap-3">
        <JobInline job={state.job} jobId={state.jobId} />
        <Button variant="outline" className="bg-card" disabled={state.running} onClick={onRun}>
          {state.running ? <Loader2 className="animate-spin" aria-hidden="true" /> : icon}
          {button}
        </Button>
      </div>
    </div>
  );
}

function JobInline({ job, jobId }: { job: AdminJob | undefined; jobId: number | null }) {
  if (!jobId) return null;
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
      Job <span className="num">{jobId}</span>
      {job ? <JobStatusPill status={job.status} /> : <Loader2 className="size-3 animate-spin" aria-hidden="true" />}
    </span>
  );
}

function useModels() {
  return useQuery({
    queryKey: ["admin", "models"],
    queryFn: () => apiRequest<{ items: ModelEntry[]; total: number; active: ModelEntry | null }>("/api/v1/admin/models"),
  });
}

function ActiveModel() {
  const models = useModels();
  const active = models.data?.active;
  const m = active?.metrics;
  return (
    <Panel>
      <PanelHeader title="Active anomaly model" />
      {models.isPending ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : models.isError ? (
        <p className="px-4 py-6 text-[13px] text-destructive">{getErrorMessage(models.error)}</p>
      ) : !active ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">No model is active. Retrain to fit one on the training split.</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-4 py-3 text-[13px] sm:grid-cols-3">
            <Item label="Version" value={active.version} />
            <Item label="Trained" value={formatDateTime(active.trained_at)} />
            <Item label="Kind" value={humanize(active.kind)} />
            <Item label="Evaluation claims" value={m?.n_claims !== undefined ? formatNumber(m.n_claims) : "–"} />
            <Item label="Planted anomalies" value={m?.n_positive !== undefined ? formatNumber(m.n_positive) : "–"} />
            <Item label="Flag threshold" value={m?.threshold !== undefined ? m.threshold.toFixed(3) : "–"} />
          </dl>
          {m?.overbilling_providers && (
            <div className="border-t px-4 py-3">
              <h3 className="mb-1.5 text-xs font-semibold text-muted-foreground">Over-billing providers</h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-4">
                <Item
                  label="Providers"
                  value={
                    Array.isArray(m.overbilling_providers.providers)
                      ? formatNumber(m.overbilling_providers.providers.length)
                      : formatNumber(m.overbilling_providers.providers as number | undefined)
                  }
                />
                <Item label="Share of top 100" value={formatPercent(m.overbilling_providers.share_of_top100)} />
                <Item label="Share of all claims" value={formatPercent(m.overbilling_providers.share_of_all)} />
                <Item label="Lift" value={m.overbilling_providers.lift !== undefined ? `${m.overbilling_providers.lift.toFixed(1)}×` : "–"} />
              </dl>
            </div>
          )}
          {models.data.items.length > 1 && (
            <div className="border-t px-4 py-3">
              <h3 className="mb-1.5 text-xs font-semibold text-muted-foreground">History</h3>
              <ul className="space-y-1 text-[13px]">
                {models.data.items.slice(0, 6).map((it) => (
                  <li key={`${it.kind}-${it.version}`} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      <span className="num font-medium">{it.version}</span>
                      <span className="text-muted-foreground">, {humanize(it.kind)}</span>
                      {it.active && <span className="ml-1.5 text-xs font-semibold text-action-approve">active</span>}
                    </span>
                    <span className="num text-xs text-muted-foreground">{formatDateTime(it.trained_at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="num truncate font-medium">{value}</dd>
    </div>
  );
}

function Evaluation() {
  const models = useModels();
  const m = models.data?.active?.metrics as ModelMetrics | undefined;
  const scenarios = Array.from(new Set(MODELS.flatMap((x) => Object.keys((m?.[x.key] as ScenarioMetrics | undefined)?.recall ?? {})))).sort();
  const precision = [
    { k: "Precision at 50", ...Object.fromEntries(MODELS.map((x) => [x.key, (m?.[x.key] as ScenarioMetrics | undefined)?.precision_at_50 ?? null])) },
    { k: "Precision at 100", ...Object.fromEntries(MODELS.map((x) => [x.key, (m?.[x.key] as ScenarioMetrics | undefined)?.precision_at_100 ?? null])) },
  ];
  const hasData = !!m && MODELS.some((x) => m[x.key]);

  return (
    <Panel>
      <PanelHeader title="Evaluation" description="How well each scorer finds the planted anomalies in the test split." />
      {models.isPending ? (
        <Skeleton className="m-4 h-56" />
      ) : !hasData ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">No evaluation metrics yet. Retrain to produce them.</p>
      ) : (
        <div className="grid gap-4 px-4 py-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="min-w-0">
            <h3 className="mb-1 text-xs font-semibold text-muted-foreground">Precision among the top-ranked claims</h3>
            <LegendKey className="mb-1" items={MODELS.map((x) => ({ label: x.label, color: x.color }))} />
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={precision} margin={{ top: 18, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="28%">
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="k" {...AXIS_PROPS} />
                  <YAxis {...AXIS_PROPS} width={40} domain={[0, 1]} tickFormatter={(v: number) => formatPercent(v, { digits: 0 })} />
                  <Tooltip
                    cursor={CURSOR_FILL}
                    content={(p) => (
                      <ChartTooltip
                        {...p}
                        rows={(d) => MODELS.map((x) => ({ label: x.label, color: x.color, value: formatPercent(d[x.key] as number | null) }))}
                      />
                    )}
                  />
                  {MODELS.map((x) => (
                    <Bar
                      key={x.key}
                      dataKey={x.key}
                      name={x.label}
                      fill={x.color}
                      radius={BAR_RADIUS_V}
                      maxBarSize={24}
                      isAnimationActive={false}
                      label={{ position: "top", fill: "var(--muted-foreground)", fontSize: 10, formatter: (v: unknown) => formatPercent(v as number, { digits: 0 }) }}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="min-w-0">
            <h3 className="mb-1 text-xs font-semibold text-muted-foreground">Recall by planted scenario</h3>
            {scenarios.length === 0 ? (
              <ChartEmpty>No scenario recall recorded.</ChartEmpty>
            ) : (
              <div className="overflow-hidden rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Scenario</TableHead>
                      {MODELS.map((x) => (
                        <TableHead key={x.key} className="text-right">
                          <span className="inline-flex items-center gap-1.5">
                            <span className="size-2 rounded-[2px]" style={{ background: x.color }} aria-hidden="true" />
                            {x.label}
                          </span>
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {scenarios.map((sc) => {
                      const values = MODELS.map((x) => (m?.[x.key] as ScenarioMetrics | undefined)?.recall?.[sc] ?? null);
                      const best = Math.max(...values.map((v) => v ?? -1));
                      return (
                        <TableRow key={sc}>
                          <TableCell>{humanize(sc)}</TableCell>
                          {values.map((v, i) => (
                            <TableCell key={MODELS[i].key} className={v !== null && v === best ? "num text-right font-semibold" : "num text-right text-muted-foreground"}>
                              {formatPercent(v)}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                    <TableRow className="bg-(--table-head) hover:bg-(--table-head)">
                      <TableCell className="text-muted-foreground">Claims flagged</TableCell>
                      {MODELS.map((x) => (
                        <TableCell key={x.key} className="num text-right">
                          {formatNumber((m?.[x.key] as ScenarioMetrics | undefined)?.flagged)}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function JobsPanel() {
  const jobs = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: () => apiRequest<{ items: AdminJob[]; total: number; counts: Record<string, number> }>("/api/v1/admin/jobs", { query: { limit: 25 } }),
    refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === "queued" || j.status === "running") ? 2500 : 15_000),
  });
  const counts = jobs.data?.counts ?? {};
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Recent jobs"
        actions={
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            {["queued", "running", "done", "failed"].map((s) => (
              <span key={s}>
                {humanize(s)} <span className="num font-semibold text-foreground">{formatNumber(counts[s] ?? 0)}</span>
              </span>
            ))}
          </div>
        }
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16 text-right">ID</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Attempts</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Finished</TableHead>
            <TableHead>Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.isPending && (
            <TableRow>
              <TableCell colSpan={7}>
                <Skeleton className="h-4 w-full" />
              </TableCell>
            </TableRow>
          )}
          {jobs.isError && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={7} className="py-6 text-center text-destructive">
                {getErrorMessage(jobs.error)}
              </TableCell>
            </TableRow>
          )}
          {jobs.data?.items.length === 0 && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={7} className="py-6 text-center text-muted-foreground">
                No jobs yet.
              </TableCell>
            </TableRow>
          )}
          {jobs.data?.items.map((j) => (
            <TableRow key={j.id} className="align-top">
              <TableCell className="num text-right text-muted-foreground">{j.id}</TableCell>
              <TableCell className="font-medium">{humanize(j.type)}</TableCell>
              <TableCell>
                <JobStatusPill status={j.status} />
              </TableCell>
              <TableCell className="num text-right">{j.attempts}</TableCell>
              <TableCell className="num text-muted-foreground">{formatDateTime(j.created_at)}</TableCell>
              <TableCell className="num text-muted-foreground">{formatDateTime(j.finished_at)}</TableCell>
              <TableCell className="max-w-[28rem] truncate text-xs" title={j.error ?? (j.result ? JSON.stringify(j.result) : undefined)}>
                {j.error ? <span className="text-destructive">{j.error}</span> : j.result ? <span className="num text-muted-foreground">{summarize(j.result)}</span> : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  );
}

function summarize(result: unknown): string {
  if (result && typeof result === "object" && !Array.isArray(result)) {
    return Object.entries(result as Record<string, unknown>)
      .filter(([, v]) => v === null || typeof v !== "object")
      .slice(0, 5)
      .map(([k, v]) => `${humanize(k)} ${v}`)
      .join(", ");
  }
  return String(result);
}
