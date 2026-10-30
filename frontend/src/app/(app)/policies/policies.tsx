"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, FileUp, Loader2, Search, Sparkles } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { LoadError } from "@/components/app-shell/states";
import { FilterSelect, Pagination } from "@/components/data-table";
import { PageHeader, Panel, PanelHeader } from "@/components/page";
import { ToneBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { Page, PolicyChunk, PolicyParams, PolicyProduct, PolicySearchResult } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { formatDateTime, formatINR, formatNumber } from "@/lib/format";
import { useJob } from "@/lib/jobs";
import { humanize } from "@/lib/labels";
import { cn } from "@/lib/utils";

const CLAUSE_TYPES = ["definition", "benefit", "exclusion", "waiting_period", "sub_limit", "general"].map((v) => ({
  value: v,
  label: humanize(v),
}));

const PARAM_LABELS: Record<string, string> = {
  room_rent_cap_pct: "Room rent cap",
  icu_cap_pct: "ICU rent cap",
  copay_pct: "Co-pay",
  deductible: "Deductible",
  initial_days: "Initial waiting period",
  listed_conditions_months: "Listed conditions waiting",
  pre_existing_months: "Pre-existing disease waiting",
};

export function Policies() {
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: () => apiRequest<Page<PolicyProduct>>("/api/v1/policies"),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const items = policies.data?.items ?? [];
  const product = items.find((p) => p.id === selected) ?? items[0];

  if (policies.isError) return <LoadError message={getErrorMessage(policies.error)} onRetry={() => policies.refetch()} />;

  return (
    <>
      <PageHeader title="Policies" description="Insurance products, their wording and the parameters the rules engine applies." />
      {policies.isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Panel className="px-4 py-10 text-center">
          <p className="text-sm font-medium">No policy products yet</p>
          <p className="mt-0.5 text-[13px] text-muted-foreground">Products appear once the reference data is loaded.</p>
        </Panel>
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" role="group" aria-label="Policy products">
            {items.map((p) => (
              <ProductCard key={p.id} product={p} active={product?.id === p.id} onSelect={() => setSelected(p.id)} />
            ))}
          </div>
          {product && <ProductDetail key={product.id} product={product} />}
        </>
      )}
    </>
  );
}

function ProductCard({ product: p, active, onSelect }: { product: PolicyProduct; active: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onSelect}
      className={cn(
        "flex flex-col items-start gap-2 rounded-lg border bg-card px-4 py-3 text-left outline-none transition-colors hover:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring",
        active && "border-primary/60 shadow-[inset_3px_0_0_var(--primary)]",
      )}
    >
      <div className="flex w-full items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{p.name}</div>
          <div className="num text-xs text-muted-foreground">
            {p.id}
            {p.version !== null && p.version !== undefined ? `, version ${p.version}` : ""}
          </div>
        </div>
        {p.diff.some((d) => d.changed) && <ToneBadge tone="--action-investigate">Changes proposed</ToneBadge>}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{p.has_wording ? `${formatNumber(p.chunks)} clauses indexed` : "No wording uploaded"}</span>
        <span>{p.approved_at ? `Parameters approved ${formatDateTime(p.approved_at)}` : "Parameters not approved"}</span>
      </div>
    </button>
  );
}

function ProductDetail({ product }: { product: PolicyProduct }) {
  const { data: user } = useMe();
  const isAdmin = user?.role === "admin";
  return (
    <Tabs defaultValue="params">
      <TabsList>
        <TabsTrigger value="params">Parameters</TabsTrigger>
        <TabsTrigger value="search">Search wording</TabsTrigger>
        <TabsTrigger value="clauses">Clauses</TabsTrigger>
      </TabsList>
      <TabsContent value="params" className="mt-3 space-y-4">
        <ParamsPanel product={product} isAdmin={isAdmin} />
        {isAdmin && <IngestPanel product={product} />}
      </TabsContent>
      <TabsContent value="search" className="mt-3">
        <SearchPanel productId={product.id} hasChunks={product.chunks > 0} />
      </TabsContent>
      <TabsContent value="clauses" className="mt-3">
        <ChunkBrowser productId={product.id} />
      </TabsContent>
    </Tabs>
  );
}

function formatParam(key: string, value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (key.endsWith("_pct")) return `${Number(value)}%${key.startsWith("room") || key.startsWith("icu") ? " of SI per day" : ""}`;
  if (key === "deductible" || key.startsWith("sub_limits.")) return formatINR(String(value));
  if (key.endsWith("_months")) return `${value} months`;
  if (key.endsWith("_days")) return `${value} days`;
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function ParamsPanel({ product, isAdmin }: { product: PolicyProduct; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const params = product.params;
  const changed = product.diff.filter((d) => d.changed);
  const approve = useMutation({
    mutationFn: () => apiRequest(`/api/v1/policies/${encodeURIComponent(product.id)}/params/approve`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Parameters approved. New claims use them from now on.");
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e) => toast.error(getErrorMessage(e)),
  });
  const extract = useMutation({
    mutationFn: () => apiRequest<{ ok?: boolean; error?: string }>(`/api/v1/policies/${encodeURIComponent(product.id)}/params/extract`, { method: "POST" }),
    onSuccess: (r) => {
      if (r.ok === false)
        toast.warning("Parameters were not extracted", {
          description: r.error === "llm_disabled" ? "Extraction needs the language model, which is not configured on this server." : r.error,
        });
      else toast.success("Parameters extracted. Review the proposed changes.");
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e) => toast.error(getErrorMessage(e)),
  });

  const rows = params ? paramRows(params) : [];

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel>
        <PanelHeader
          title="Approved parameters"
          description={product.approved_by ? `Approved by ${product.approved_by}, ${formatDateTime(product.approved_at)}` : "In force for the rules engine"}
        />
        {rows.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">No parameters set for this product.</p>
        ) : (
          <dl className="divide-y text-[13px]">
            {rows.map((r) => (
              <div key={r.key} className="flex items-baseline justify-between gap-4 px-4 py-2">
                <dt className="text-muted-foreground">
                  {r.label}
                  {r.clause && <span className="num ml-1.5 text-xs">cl. {r.clause}</span>}
                </dt>
                <dd className="num text-right font-medium">{r.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title="Proposed changes"
          description="Parameters extracted from the latest wording, compared with what is approved."
          actions={
            isAdmin && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" className="bg-card" disabled={extract.isPending || product.chunks === 0} onClick={() => extract.mutate()}>
                  {extract.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles data-icon="inline-start" aria-hidden="true" />}
                  Extract
                </Button>
                <Button size="sm" disabled={approve.isPending || !product.proposed} onClick={() => approve.mutate()}>
                  {approve.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <CircleCheck data-icon="inline-start" aria-hidden="true" />}
                  Approve
                </Button>
              </div>
            )
          }
        />
        {product.diff.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">
            {product.proposed ? "The proposal matches the approved parameters." : "Nothing proposed. Extract parameters from the ingested wording to compare."}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Parameter</TableHead>
                <TableHead className="text-right">Approved</TableHead>
                <TableHead className="text-right">Proposed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {product.diff.map((d) => (
                <TableRow key={d.param} className={cn(d.changed && "bg-action-investigate/6")}>
                  <TableCell>
                    {paramLabel(d.param)}
                    {d.changed && <span className="ml-2 text-xs font-semibold text-action-investigate">changed</span>}
                  </TableCell>
                  <TableCell className="num text-right text-muted-foreground">{formatParam(d.param, d.current)}</TableCell>
                  <TableCell className={cn("num text-right", d.changed && "font-semibold")}>{formatParam(d.param, d.proposed)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {changed.length > 0 && (
          <p className="border-t px-4 py-2 text-xs text-muted-foreground">
            {changed.length} {changed.length === 1 ? "parameter differs" : "parameters differ"}. Approving replaces the approved set.
          </p>
        )}
      </Panel>
    </div>
  );
}

function paramLabel(key: string) {
  if (key.startsWith("sub_limits.")) return `Sub-limit, ${key.slice("sub_limits.".length)}`;
  return PARAM_LABELS[key] ?? humanize(key);
}

function paramRows(p: PolicyParams) {
  const refs = p.clause_refs ?? {};
  const rows = (Object.keys(PARAM_LABELS) as (keyof PolicyParams)[]).map((k) => ({
    key: k,
    label: PARAM_LABELS[k],
    value: formatParam(k, p[k]),
    clause: refs[k],
  }));
  for (const [code, limit] of Object.entries(p.sub_limits ?? {})) {
    rows.push({ key: `sub_limits.${code}` as keyof PolicyParams, label: `Sub-limit, ${code}`, value: formatINR(String(limit)), clause: refs.sub_limits });
  }
  return rows;
}

function IngestPanel({ product }: { product: PolicyProduct }) {
  const queryClient = useQueryClient();
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const job = useJob(jobId, {
    onFinish: (j) => {
      if (j.status === "failed") toast.error("Ingestion failed", { description: j.error ?? undefined });
      else toast.success("Wording ingested");
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
      void queryClient.invalidateQueries({ queryKey: ["chunks", product.id] });
    },
  });
  const ingest = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (file) form.append("file", file);
      return apiRequest<{ job_id: number }>(`/api/v1/policies/${encodeURIComponent(product.id)}/ingest`, { method: "POST", form });
    },
    onSuccess: (r) => {
      setJobId(r.job_id);
      setFile(null);
    },
  });
  const running = ingest.isPending || (jobId !== null && job.data?.status !== "done" && job.data?.status !== "failed");

  return (
    <Panel>
      <PanelHeader
        title="Ingest wording"
        description="Upload a new policy wording PDF, or re-index the current one. Clauses are chunked and indexed for search."
      />
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <label
          htmlFor={inputId}
          className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border bg-card px-2.5 text-sm font-medium hover:bg-muted has-focus-visible:ring-2 has-focus-visible:ring-ring"
        >
          <FileUp className="size-4" aria-hidden="true" />
          {file ? file.name : "Choose PDF"}
          <input id={inputId} type="file" accept="application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <Button onClick={() => ingest.mutate()} disabled={running || (!file && !product.has_wording)}>
          {running && <Loader2 className="animate-spin" aria-hidden="true" />}
          {file ? "Upload and ingest" : "Re-ingest current wording"}
        </Button>
        {jobId !== null && job.data && (
          <span className="text-[13px] text-muted-foreground" aria-live="polite">
            Job <span className="num">{jobId}</span>: {humanize(job.data.status)}
          </span>
        )}
        {ingest.isError && <span className="text-[13px] text-destructive">{getErrorMessage(ingest.error)}</span>}
      </div>
    </Panel>
  );
}

function SearchPanel({ productId, hasChunks }: { productId: string; hasChunks: boolean }) {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const search = useQuery({
    queryKey: ["policy-search", productId, query],
    queryFn: () => apiRequest<Page<PolicySearchResult>>(`/api/v1/policies/${encodeURIComponent(productId)}/search`, { query: { q: query } }),
    enabled: query.length > 0,
  });
  return (
    <Panel>
      <PanelHeader title="Search the wording" description="Hybrid search: vector similarity and keyword match, fused by rank." />
      <form
        className="flex gap-2 border-b px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(draft.trim());
        }}
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="For example: room rent limit for ICU"
            aria-label="Search the policy wording"
            className="h-9 pl-8"
            disabled={!hasChunks}
          />
        </div>
        <Button type="submit" disabled={!draft.trim() || !hasChunks}>
          Search
        </Button>
      </form>
      {!hasChunks ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">This product has no indexed wording yet.</p>
      ) : !query ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">Results show the clause, where it sits in the wording, and how each method ranked it.</p>
      ) : search.isPending ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : search.isError ? (
        <p className="px-4 py-6 text-[13px] text-destructive">{getErrorMessage(search.error)}</p>
      ) : search.data.items.length === 0 ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">No clauses match “{query}”.</p>
      ) : (
        <ol className="divide-y">
          {search.data.items.map((r) => (
            <li key={r.id} className="px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-baseline gap-2 text-[13px]">
                  <span className="num font-semibold">Clause {r.clause_no ?? "–"}</span>
                  {r.clause_type && <ToneBadge className="font-medium">{humanize(r.clause_type)}</ToneBadge>}
                  <span className="truncate text-xs text-muted-foreground">{r.section_path}</span>
                </div>
                <span className="num text-xs text-muted-foreground">
                  score {r.score.toFixed(4)}, vector #{r.vector_rank ?? "–"}, keyword #{r.keyword_rank ?? "–"}
                </span>
              </div>
              <p className="mt-1 line-clamp-4 max-w-[90ch] text-[13px] leading-5 whitespace-pre-line text-foreground/90">{r.text}</p>
              {r.definitions && r.definitions.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Defined terms attached: {r.definitions.map((d) => d.clause_no).filter(Boolean).join(", ")}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

function ChunkBrowser({ productId }: { productId: string }) {
  const [page, setPage] = useState(1);
  const [clauseType, setClauseType] = useState("");
  const chunks = useQuery({
    queryKey: ["chunks", productId, page, clauseType],
    queryFn: () =>
      apiRequest<Page<PolicyChunk>>(`/api/v1/policies/${encodeURIComponent(productId)}/chunks`, {
        query: { page, page_size: 25, clause_type: clauseType },
      }),
    placeholderData: keepPreviousData,
  });
  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-2.5">
        <h2 className="text-sm font-semibold">Clauses</h2>
        <FilterSelect
          label="Type"
          value={clauseType}
          onChange={(v) => {
            setClauseType(v);
            setPage(1);
          }}
          options={CLAUSE_TYPES}
        />
      </div>
      {chunks.isPending ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : chunks.isError ? (
        <p className="px-4 py-6 text-[13px] text-destructive">{getErrorMessage(chunks.error)}</p>
      ) : chunks.data.items.length === 0 ? (
        <p className="px-4 py-6 text-[13px] text-muted-foreground">No clauses{clauseType ? ` of type ${humanize(clauseType).toLowerCase()}` : ""}.</p>
      ) : (
        <ul className="divide-y">
          {chunks.data.items.map((c) => (
            <li key={c.id} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
              <div className="text-[13px]">
                <div className="num font-semibold">{c.clause_no ?? "–"}</div>
                <div className="text-xs text-muted-foreground">
                  {c.clause_type ? humanize(c.clause_type) : ""}
                  {c.page ? `, p. ${c.page}` : ""}
                </div>
              </div>
              <div className="min-w-0">
                {c.section_path && <div className="mb-0.5 truncate text-xs text-muted-foreground">{c.section_path}</div>}
                <p className="max-w-[90ch] text-[13px] leading-5 whitespace-pre-line">{c.text}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pagination page={page} pageSize={25} total={chunks.data?.total} onPage={setPage} isFetching={chunks.isFetching} />
    </Panel>
  );
}
