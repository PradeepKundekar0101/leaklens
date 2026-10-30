import { cn } from "@/lib/utils";

/** A lens over a drop: the product's one-line idea, at 20px. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={cn("size-6 shrink-0", className)}
      fill="none"
    >
      <rect width="24" height="24" rx="5" className="fill-primary" />
      <circle cx="11" cy="11" r="5.25" className="stroke-primary-foreground" strokeWidth="1.75" />
      <path d="M15 15l3.5 3.5" className="stroke-primary-foreground" strokeWidth="1.75" strokeLinecap="round" />
      <path
        d="M11 7.9c1.05 1.3 1.75 2.3 1.75 3.15a1.75 1.75 0 0 1-3.5 0c0-.85.7-1.85 1.75-3.15z"
        className="fill-primary-foreground"
      />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">LeakLens</span>
    </span>
  );
}
