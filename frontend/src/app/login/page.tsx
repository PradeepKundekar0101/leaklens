import type { Metadata } from "next";
import { Suspense } from "react";

import { Wordmark } from "@/components/brand";

import { BillExcerpt } from "./bill-excerpt";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="grid min-h-dvh bg-card lg:grid-cols-[minmax(28rem,5fr)_7fr]">
      <div className="flex flex-col px-6 py-6 sm:px-10">
        <Wordmark />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[22rem]">
            <h1 className="text-2xl leading-8 font-semibold tracking-[-0.015em]">Sign in to LeakLens</h1>
            <p className="mt-1 text-sm text-muted-foreground">Use your work email and password.</p>
            <Suspense>
              <LoginForm showDemoAccounts={process.env.NODE_ENV === "development"} />
            </Suspense>
          </div>
        </div>
      </div>
      <div className="hidden border-l bg-sidebar lg:flex lg:items-center lg:justify-center lg:px-12 lg:py-10">
        <BillExcerpt />
      </div>
    </div>
  );
}
