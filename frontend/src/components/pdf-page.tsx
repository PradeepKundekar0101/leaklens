"use client";

import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";

export interface BBox {
  l: number;
  t: number;
  r: number;
  b: number;
  page?: number;
  page_width?: number;
  page_height?: number;
}

let pdfjsPromise: Promise<typeof import("pdfjs-dist")> | null = null;
function loadPdfjs() {
  pdfjsPromise ??= import("pdfjs-dist").then((pdfjs) => {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
    return pdfjs;
  });
  return pdfjsPromise;
}

/** Loads a PDF once per URL. */
export function usePdf(url: string | undefined) {
  const [state, setState] = useState<{ doc: PDFDocumentProxy | null; error: string | null; url?: string }>({ doc: null, error: null });
  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    let task: { destroy: () => Promise<void> } | null = null;
    loadPdfjs()
      .then((pdfjs) => {
        const loading = pdfjs.getDocument({ url, withCredentials: true });
        task = loading;
        return loading.promise;
      })
      .then((doc) => {
        if (!cancelled) setState({ doc, error: null, url });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ doc: null, error: e instanceof Error ? e.message : "Could not open the PDF.", url });
      });
    return () => {
      cancelled = true;
      void (task as { destroy: () => Promise<void> } | null)?.destroy();
    };
  }, [url]);
  return state.url === url ? state : { doc: null, error: null };
}

/**
 * Renders one PDF page to a canvas sized to its container, with an optional highlight box
 * given in PDF points (top-left origin, as the backend stores line-item provenance).
 */
export function PdfPage({ doc, pageNumber, highlight }: { doc: PDFDocumentProxy; pageNumber: number; highlight?: BBox | null }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState<{ cssWidth: number; pageWidth: number; pageHeight: number } | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!width || !canvasRef.current) return;
    let cancelled = false;
    let task: { cancel: () => void; promise: Promise<void> } | null = null;
    void doc.getPage(pageNumber).then((page) => {
      if (cancelled || !canvasRef.current) return;
      const base = page.getViewport({ scale: 1 });
      const dpr = window.devicePixelRatio || 1;
      const scale = width / base.width;
      const viewport = page.getViewport({ scale: scale * dpr });
      const canvas = canvasRef.current;
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${Math.floor(base.height * scale)}px`;
      task = page.render({ canvas, viewport });
      task.promise
        .then(() => !cancelled && setSize({ cssWidth: width, pageWidth: base.width, pageHeight: base.height }))
        .catch(() => undefined);
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [doc, pageNumber, width]);

  const scale = size ? size.cssWidth / (highlight?.page_width ?? size.pageWidth) : 1;
  const markRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [size, highlight]);
  return (
    <div ref={wrapRef} className="relative w-full">
      {!size && <Skeleton className="absolute inset-0 min-h-96" />}
      <canvas ref={canvasRef} className="block rounded-sm bg-white shadow-sm ring-1 ring-border" />
      {size && highlight && (
        <div
          ref={markRef}
          aria-hidden="true"
          className="pointer-events-none absolute rounded-[2px] bg-chart-2/20 ring-2 ring-chart-2"
          style={{
            left: highlight.l * scale - 2,
            top: highlight.t * scale - 2,
            width: (highlight.r - highlight.l) * scale + 4,
            height: (highlight.b - highlight.t) * scale + 4,
          }}
        />
      )}
    </div>
  );
}
