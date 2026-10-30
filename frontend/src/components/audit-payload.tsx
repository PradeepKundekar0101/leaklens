import { formatINR } from "@/lib/format";
import { humanize } from "@/lib/labels";

const MONEY = /(amount|payable|leakage|claimed|final|price)/i;

/** Compact key/value rendering of an audit payload; nested values are shown as JSON. */
export function AuditPayload({ payload, max = 8 }: { payload: Record<string, unknown> | null; max?: number }) {
  if (!payload) return null;
  const entries = Object.entries(payload).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (entries.length === 0) return null;
  return (
    <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs">
      {entries.slice(0, max).map(([k, v]) => (
        <div key={k} className="flex min-w-0 max-w-full gap-1">
          <dt className="shrink-0 text-muted-foreground">{humanize(k)}</dt>
          <dd className="num min-w-0 truncate font-medium" title={typeof v === "object" ? JSON.stringify(v) : String(v)}>
            {render(k, v)}
          </dd>
        </div>
      ))}
      {entries.length > max && <div className="text-muted-foreground">+{entries.length - max} more</div>}
    </dl>
  );
}

function render(key: string, value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value);
  const s = String(value);
  if (MONEY.test(key) && /^-?\d+(\.\d+)?$/.test(s)) return formatINR(s);
  return s;
}
