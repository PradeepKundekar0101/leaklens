"use client";

import { LogOut, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";

import { Wordmark } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getErrorMessage } from "@/lib/api/errors";
import { useLogout, useMe } from "@/lib/auth/hooks";
import { ROLE_LABELS } from "@/lib/auth/roles";

import { HOME_PATH, navItemForPath } from "./nav";
import { SidebarNav } from "./sidebar-nav";
import { AccessDenied, LoadError } from "./states";

/**
 * Authenticated chrome: sidebar, top bar and the client-side session guard.
 *
 * The frame and the page render immediately (so navigations are instant and the static
 * shell is prerendered); only the user-dependent parts wait for /auth/me. The proxy has
 * already redirected requests without a session cookie, so the remaining case is an
 * expired cookie, which SessionGate handles.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <SidebarContents />
      </aside>
      <div className="lg:pl-56">
        <TopBar />
        <main id="main" className="px-4 py-5 sm:px-6 lg:py-6 2xl:px-8">
          <Suspense fallback={<ContentSkeleton />}>
            <SessionGate>{children}</SessionGate>
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function SessionGate({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();

  const signedOut = me.isSuccess && me.data === null;
  useEffect(() => {
    if (!signedOut) return;
    const next = pathname && pathname !== HOME_PATH ? `?next=${encodeURIComponent(pathname)}` : "";
    router.replace(`/login${next}`);
  }, [signedOut, pathname, router]);

  if (me.isError) return <LoadError message={getErrorMessage(me.error)} onRetry={() => me.refetch()} />;
  if (signedOut) return <ContentSkeleton />;

  const user = me.data;
  const section = navItemForPath(pathname);
  if (user && section && !section.roles.includes(user.role)) {
    return <AccessDenied section={section.label} role={ROLE_LABELS[user.role]} />;
  }
  return children;
}

function SidebarContents({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      <div className="flex h-12 shrink-0 items-center px-4">
        <Link
          href={HOME_PATH}
          onClick={onNavigate}
          className="-mx-1 rounded-md px-1 py-0.5 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <Wordmark />
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-2.5 pt-3">
        <Suspense fallback={<NavSkeleton />}>
          <RoleNav onNavigate={onNavigate} />
        </Suspense>
      </div>
    </>
  );
}

function RoleNav({ onNavigate }: { onNavigate?: () => void }) {
  const { data: user } = useMe();
  if (!user) return <NavSkeleton />;
  return <SidebarNav role={user.role} onNavigate={onNavigate} />;
}

function TopBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();

  const signOut = () =>
    logout.mutate(undefined, {
      onSuccess: () => router.replace("/login"),
      onError: (error) => toast.error(getErrorMessage(error)),
    });

  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b bg-canvas/90 px-4 backdrop-blur-sm supports-backdrop-filter:bg-canvas/75 sm:px-6 2xl:px-8">
      <a
        href="#main"
        className="sr-only rounded-md bg-card px-3 py-1.5 text-sm font-medium focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>

      <Button
        variant="ghost"
        size="icon"
        className="-ml-2 lg:hidden"
        aria-label="Open navigation"
        onClick={() => setMenuOpen(true)}
      >
        <Menu aria-hidden="true" />
      </Button>
      <Link href={HOME_PATH} className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden">
        <Wordmark />
      </Link>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-64 gap-0 bg-sidebar p-0 sm:max-w-64">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">Sections available to your role</SheetDescription>
          <div className="flex h-full flex-col">
            <SidebarContents onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="ml-auto flex min-w-0 items-center gap-1">
        <div className="mr-2 flex min-w-0 items-center gap-2">
          {user ? (
            <>
              <span className="hidden truncate text-sm font-medium sm:block" title={user.email}>
                {user.name}
              </span>
              <RoleBadge role={ROLE_LABELS[user.role]} />
            </>
          ) : (
            <Skeleton className="h-5 w-36" />
          )}
        </div>
        <ThemeToggle />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Sign out"
              onClick={signOut}
              disabled={!user || logout.isPending}
            >
              <LogOut aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Sign out</TooltipContent>
        </Tooltip>
      </div>
    </header>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-flex h-5 items-center rounded-[4px] border border-primary/25 bg-primary/8 px-1.5 text-xs leading-none font-semibold text-primary">
      {role}
    </span>
  );
}

function NavSkeleton() {
  return (
    <div className="flex flex-col gap-0.5" aria-hidden="true">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex h-8 items-center gap-2.5 px-2.5">
          <Skeleton className="size-4 bg-sidebar-border" />
          <Skeleton className="h-3.5 w-20 bg-sidebar-border" />
        </div>
      ))}
    </div>
  );
}

function ContentSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <Skeleton className="mt-4 h-64 w-full" />
    </div>
  );
}
