"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, CircleAlert, ExternalLink, FileText, ImageIcon, Loader2, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";

import { ParseStatusPill } from "@/components/claim-status";
import { Panel, PanelHeader } from "@/components/page";
import { type BBox, PdfPage, usePdf } from "@/components/pdf-page";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { ClaimDetail, ClaimDocument, LineItem } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { hasRole } from "@/lib/auth/roles";
import { claimQueryKey } from "@/lib/claims";
import { formatDateTime, formatNumber } from "@/lib/format";
import { DOC_TYPE_LABELS, humanize } from "@/lib/labels";
import { cn } from "@/lib/utils";

const MAX_BYTES = 15 * 1024 * 1024;

export function DocumentsTab({
  claim,
  selectedLine,
  onSelectLine,
}: {
  claim: ClaimDetail;
  selectedLine: number | null;
  onSelectLine: (id: number | null) => void;
}) {
  const { data: user } = useMe();
  const canUpload = hasRole(user?.role, ["adjuster", "admin"]);
  const line = selectedLine !== null ? claim.line_items.find((l) => l.id === selectedLine) ?? null : null;
  const [docId, setDocId] = useState<number | null>(null);

  // Selecting a line item jumps to its source document.
  const activeDocId = line?.document_id ?? docId ?? claim.documents[0]?.id ?? null;
  const doc = claim.documents.find((d) => d.id === activeDocId) ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <div className="space-y-4">
        <Panel>
          <PanelHeader title="Documents" />
          {claim.documents.length === 0 ? (
            <p className="px-4 py-5 text-[13px] text-muted-foreground">No documents on this claim yet.</p>
          ) : (
            <ul className="divide-y">
              {claim.documents.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setDocId(d.id);
                      if (line && line.document_id !== d.id) onSelectLine(null);
                    }}
                    aria-current={d.id === activeDocId ? "true" : undefined}
                    className={cn(
                      "flex w-full flex-col gap-1 px-4 py-2.5 text-left outline-none hover:bg-accent/60 focus-visible:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
                      d.id === activeDocId && "bg-accent",
                    )}
                  >
                    <span className="flex items-center gap-2 text-[13px] font-medium">
                      {d.content_type === "application/pdf" ? (
                        <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                      ) : (
                        <ImageIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                      )}
                      <span className="truncate">{d.filename || `Document ${d.id}`}</span>
                    </span>
                    <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      {DOC_TYPE_LABELS[d.doc_type] ?? humanize(d.doc_type)}
                      {d.pages ? `, ${formatNumber(d.pages)} ${d.pages === 1 ? "page" : "pages"}` : ""}
                      {d.route && `, ${humanize(d.route)}`}
                      <ParseStatusPill status={d.parse_status} />
                    </span>
                    {d.issues.length > 0 && (
                      <span className="flex items-start gap-1 text-xs text-action-investigate">
                        <CircleAlert className="mt-px size-3 shrink-0" aria-hidden="true" />
                        <span>{d.issues.join("; ")}</span>
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        {canUpload && <UploadBox claimId={claim.id} />}
      </div>

      <DocumentViewer doc={doc} claimId={claim.id} line={line && line.document_id === doc?.id ? line : null} />
    </div>
  );
}

function DocumentViewer({ doc, claimId, line }: { doc: ClaimDocument | null; claimId: string; line: LineItem | null }) {
  const link = useQuery({
    queryKey: ["document-url", claimId, doc?.id],
    queryFn: () =>
      apiRequest<{ url: string; expires_in: number; content_type: string }>(
        `/api/v1/claims/${encodeURIComponent(claimId)}/documents/${doc!.id}/url`,
      ),
    enabled: !!doc,
    // Links are signed for five minutes.
    staleTime: 4 * 60_000,
    refetchInterval: 4 * 60_000,
  });

  if (!doc) {
    return (
      <Panel className="flex min-h-80 items-center justify-center px-6 text-center text-[13px] text-muted-foreground">
        Select a document to view it.
      </Panel>
    );
  }

  const bbox = (line?.bbox ?? null) as BBox | null;
  const isPdf = (link.data?.content_type ?? doc.content_type) === "application/pdf";

  return (
    <Panel className="min-w-0">
      <PanelHeader
        title={doc.filename || `Document ${doc.id}`}
        description={
          line
            ? `Highlighting "${line.description}"${line.page ? ` on page ${line.page}` : ""}${bbox ? "" : " (no position recorded)"}.`
            : `Uploaded ${formatDateTime(doc.created_at)}`
        }
        actions={
          link.data && (
            <Button asChild variant="ghost" size="sm">
              <a href={link.data.url} target="_blank" rel="noreferrer">
                <ExternalLink data-icon="inline-start" aria-hidden="true" />
                Open
              </a>
            </Button>
          )
        }
      />
      <div className="bg-muted/40 p-4">
        {link.isPending ? (
          <Skeleton className="h-[32rem] w-full" />
        ) : link.isError ? (
          <p className="py-16 text-center text-[13px] text-destructive">{getErrorMessage(link.error)}</p>
        ) : isPdf ? (
          <PdfViewer url={link.data.url} pages={doc.pages ?? 1} focusPage={line?.page ?? bbox?.page ?? null} bbox={bbox} />
        ) : (
          <ImageViewer url={link.data.url} bbox={bbox} alt={doc.filename ?? "Claim document"} />
        )}
      </div>
    </Panel>
  );
}

function PdfViewer({ url, pages, focusPage, bbox }: { url: string; pages: number; focusPage: number | null; bbox: BBox | null }) {
  const { doc, error } = usePdf(url);
  const [page, setPage] = useState(focusPage ?? 1);
  const [lastFocus, setLastFocus] = useState(focusPage);
  if (focusPage !== lastFocus) {
    setLastFocus(focusPage);
    if (focusPage) setPage(focusPage);
  }
  const total = doc?.numPages ?? pages;
  if (error) return <p className="py-16 text-center text-[13px] text-destructive">{error}</p>;
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-2 flex items-center justify-center gap-2 text-[13px] text-muted-foreground">
        <Button variant="outline" size="icon-sm" className="bg-card" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          <ChevronLeft aria-hidden="true" />
        </Button>
        <span className="num min-w-24 text-center">
          Page {page} of {total}
        </span>
        <Button variant="outline" size="icon-sm" className="bg-card" aria-label="Next page" disabled={page >= total} onClick={() => setPage(page + 1)}>
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
      {doc ? (
        <PdfPage doc={doc} pageNumber={page} highlight={bbox && (bbox.page ?? focusPage) === page ? bbox : null} />
      ) : (
        <Skeleton className="h-[32rem] w-full" />
      )}
    </div>
  );
}

function ImageViewer({ url, bbox, alt }: { url: string; bbox: BBox | null; alt: string }) {
  const [natural, setNatural] = useState<{ w: number; h: number; cssW: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => el.naturalWidth && setNatural({ w: el.naturalWidth, h: el.naturalHeight, cssW: el.clientWidth }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const scale = natural ? natural.cssW / (bbox?.page_width ?? natural.w) : 1;
  return (
    <div className="relative mx-auto max-w-3xl">
      {/* eslint-disable-next-line @next/next/no-img-element -- signed, short-lived URL served through the API */}
      <img
        ref={imgRef}
        src={url}
        alt={alt}
        className="block w-full rounded-sm bg-white shadow-sm ring-1 ring-border"
        onLoad={(e) => {
          const el = e.currentTarget;
          setNatural({ w: el.naturalWidth, h: el.naturalHeight, cssW: el.clientWidth });
        }}
      />
      {natural && bbox && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute rounded-[2px] bg-chart-2/20 ring-2 ring-chart-2"
          style={{
            left: bbox.l * scale - 2,
            top: bbox.t * scale - 2,
            width: (bbox.r - bbox.l) * scale + 4,
            height: (bbox.b - bbox.t) * scale + 4,
          }}
        />
      )}
    </div>
  );
}

export function UploadBox({ claimId }: { claimId: string }) {
  const queryClient = useQueryClient();
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > MAX_BYTES) throw new Error(`${file.name} is larger than 15 MB.`);
      const form = new FormData();
      form.append("file", file);
      return apiRequest<{ id: number; job_id: number }>(`/api/v1/claims/${encodeURIComponent(claimId)}/documents`, {
        method: "POST",
        form,
      });
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: claimQueryKey(claimId) }),
  });

  const handleFiles = async (files: FileList | File[]) => {
    setErrors([]);
    const list = Array.from(files);
    const failed: string[] = [];
    for (const file of list) {
      try {
        await upload.mutateAsync(file);
      } catch (e) {
        failed.push(`${file.name}: ${getErrorMessage(e)}`);
      }
    }
    setErrors(failed);
    const ok = list.length - failed.length;
    if (ok > 0) toast.success(ok === 1 ? "Document uploaded. Parsing has started." : `${ok} documents uploaded. Parsing has started.`);
  };

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed bg-card px-4 py-5 text-center transition-colors has-focus-visible:ring-2 has-focus-visible:ring-ring",
          dragging ? "border-primary bg-primary/5" : "hover:border-primary/50",
        )}
      >
        {upload.isPending ? (
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
        ) : (
          <Upload className="size-5 text-muted-foreground" aria-hidden="true" />
        )}
        <span className="text-[13px] font-medium">{upload.isPending ? "Uploading" : "Drop files or choose"}</span>
        <span className="text-xs text-muted-foreground">PDF, PNG or JPEG, up to 15 MB each</span>
        <input
          id={inputId}
          type="file"
          multiple
          accept="application/pdf,image/png,image/jpeg"
          className="sr-only"
          disabled={upload.isPending}
          onChange={(e) => {
            if (e.target.files?.length) void handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
      {errors.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-destructive" role="alert">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
