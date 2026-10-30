"use client";

import { cn } from "@/lib/utils";

/**
 * Shared Recharts styling. Colours are CSS variables (validated in globals.css) so light
 * and dark mode each use their own steps. Marks are thin, grids recessive and solid.
 */
export const AXIS_PROPS = {
  stroke: "var(--chart-grid)",
  tick: { fill: "var(--chart-axis)", fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: "var(--chart-grid)" },
} as const;

export const GRID_PROPS = {
  stroke: "var(--chart-grid)",
  strokeDasharray: undefined,
  vertical: false,
} as const;

/** Rounded data-end, square at the baseline (horizontal bars grow right). */
export const BAR_RADIUS_H: [number, number, number, number] = [0, 4, 4, 0];
/** Rounded data-end for vertical columns. */
export const BAR_RADIUS_V: [number, number, number, number] = [4, 4, 0, 0];

export const CURSOR_FILL = { fill: "var(--accent)", opacity: 0.6 };

export function ChartTooltip({
  active,
  payload,
  label,
  formatLabel,
  rows,
}: {
  active?: boolean;
  payload?: readonly { payload?: unknown }[];
  label?: unknown;
} & {
  formatLabel?: (label: unknown) => React.ReactNode;
  rows: (payload: Record<string, unknown>) => { label: string; value: React.ReactNode; color?: string }[];
}) {
  if (!active || !payload?.length) return null;
  const datum = payload[0]?.payload as Record<string, unknown>;
  return (
    <div className="min-w-40 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      {label !== undefined && label !== null && (
        <div className="mb-1 font-semibold">{formatLabel ? formatLabel(label) : String(label)}</div>
      )}
      <dl className="space-y-0.5">
        {rows(datum).map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <dt className="flex items-center gap-1.5 text-muted-foreground">
              {r.color && <span className="size-2 rounded-[2px]" style={{ background: r.color }} aria-hidden="true" />}
              {r.label}
            </dt>
            <dd className="num font-semibold">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function LegendKey({ items, className }: { items: { label: string; color: string; dashed?: boolean }[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground", className)}>
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          {i.dashed ? (
            <span className="w-3.5 border-t-2 border-dashed" style={{ borderColor: i.color }} aria-hidden="true" />
          ) : (
            <span className="size-2.5 rounded-[2px]" style={{ background: i.color }} aria-hidden="true" />
          )}
          {i.label}
        </li>
      ))}
    </ul>
  );
}

export function ChartEmpty({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex h-full min-h-40 items-center justify-center px-6 text-center text-[13px] text-muted-foreground", className)}>
      {children}
    </div>
  );
}
