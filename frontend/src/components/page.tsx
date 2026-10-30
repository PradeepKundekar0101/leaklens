import { Hammer } from "lucide-react";

import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0">
        <h1 className="text-xl leading-7 font-semibold tracking-[-0.01em] text-foreground">{title}</h1>
        {description && <p className="mt-0.5 max-w-[72ch] text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A white work surface on the canvas. Tables and panels sit in these. */
export function Panel({ className, ...props }: React.ComponentProps<"section">) {
  return <section className={cn("rounded-lg border bg-card text-card-foreground", className)} {...props} />;
}

export function PanelHeader({
  title,
  description,
  actions,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b px-4 py-3", className)}>
      <div className="min-w-0">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

/** Stage-1 placeholder: says what the page will do so reviewers can check the scope. */
export function ComingSoon({ items, className }: { items: string[]; className?: string }) {
  return (
    <Panel className={cn("border-dashed bg-card/60", className)}>
      <div className="flex gap-3 px-4 py-4">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Hammer className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">Coming soon</h2>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            This page is being connected to the LeakLens API. It will show:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] text-foreground/90 marker:text-muted-foreground">
            {items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
