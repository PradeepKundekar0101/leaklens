"use client";

import { CircleAlert, Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { safeNextPath } from "@/components/app-shell/nav";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/api/errors";
import { useLogin } from "@/lib/auth/hooks";
import { ROLE_LABELS, type Role } from "@/lib/auth/roles";

/** Seeded by backend/scripts/seed_users.py. Shown in local development only. */
const DEMO_ACCOUNTS: { role: Role; email: string }[] = [
  { role: "adjuster", email: "adjuster@leaklens.local" },
  { role: "auditor", email: "auditor@leaklens.local" },
  { role: "manager", email: "manager@leaklens.local" },
  { role: "admin", email: "admin@leaklens.local" },
];
const DEMO_PASSWORD = "LeakLens!2026";

export function LoginForm({ showDemoAccounts }: { showDemoAccounts: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));

  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const submitRef = useRef<HTMLButtonElement>(null);
  const errorId = useId();

  // Next keeps visited routes alive (hidden) for back/forward. When this page is hidden
  // after a successful sign-in, clear it so a later sign-out shows a fresh form.
  const { reset } = login;
  useEffect(
    () => () => {
      reset();
      setPassword("");
    },
    [reset],
  );

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    login.mutate({ email: email.trim(), password }, { onSuccess: () => router.replace(next) });
  };

  const fill = (account: (typeof DEMO_ACCOUNTS)[number]) => {
    setEmail(account.email);
    setPassword(DEMO_PASSWORD);
    login.reset();
    submitRef.current?.focus();
  };

  const busy = login.isPending || login.isSuccess;
  const error = login.isError ? getErrorMessage(login.error) : null;

  return (
    <>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            className="h-9"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            className="h-9"
          />
        </div>

        {error && (
          <Alert variant="destructive" id={errorId} aria-live="polite">
            <CircleAlert aria-hidden="true" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Button ref={submitRef} type="submit" size="lg" className="h-9 w-full" disabled={busy}>
          {busy && <Loader2 className="animate-spin" aria-hidden="true" />}
          {busy ? "Signing in" : "Sign in"}
        </Button>
      </form>

      {showDemoAccounts && (
        <div className="mt-8 border-t pt-5">
          <h2 className="text-[13px] font-semibold">Demo accounts</h2>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Local development only. Choose a role to fill in its credentials.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.role}
                type="button"
                onClick={() => fill(account)}
                className="group flex min-w-0 flex-col items-start rounded-md border bg-card px-3 py-2 text-left outline-none transition-colors hover:border-primary/40 hover:bg-primary/[0.04] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
              >
                <span className="text-[13px] font-semibold">{ROLE_LABELS[account.role]}</span>
                <span className="w-full truncate text-xs text-muted-foreground">{account.email}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
