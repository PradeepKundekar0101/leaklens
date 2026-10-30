"use client";

import { Lock, RefreshCw, ServerCrash } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

import { HOME_PATH } from "./nav";

export function AccessDenied({ section, role }: { section: string; role: string }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-20 text-center">
      <div className="mb-4 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock className="size-5" aria-hidden="true" />
      </div>
      <h1 className="text-lg font-semibold">{section} is not available to your role</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Your role is {role}. Ask an admin if you need access.
      </p>
      <Button asChild variant="outline" className="mt-5">
        <Link href={HOME_PATH}>Go to claims</Link>
      </Button>
    </div>
  );
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex justify-center py-20">
      <div className="flex max-w-sm flex-col items-center text-center">
        <div className="mb-4 flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <ServerCrash className="size-5" aria-hidden="true" />
        </div>
        <h1 className="text-lg font-semibold">LeakLens could not load</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">{message}</p>
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          <RefreshCw data-icon="inline-start" aria-hidden="true" />
          Try again
        </Button>
      </div>
    </div>
  );
}
