import {
  Building2,
  ClipboardList,
  History,
  LayoutDashboard,
  type LucideIcon,
  ScrollText,
  SlidersHorizontal,
} from "lucide-react";

import type { Role } from "@/lib/auth/roles";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  roles: readonly Role[];
}

const ALL: readonly Role[] = ["adjuster", "auditor", "manager", "admin"];

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/claims", label: "Claims", icon: ClipboardList, roles: ALL },
  { href: "/providers", label: "Providers", icon: Building2, roles: ["auditor", "manager", "admin"] },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["manager", "auditor", "admin"] },
  { href: "/policies", label: "Policies", icon: ScrollText, roles: ALL },
  { href: "/audit", label: "Audit", icon: History, roles: ["auditor", "manager", "admin"] },
  { href: "/admin", label: "Admin", icon: SlidersHorizontal, roles: ["manager", "admin"] },
];

export function navItemsFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

/** The nav section a path belongs to (`/claims/123` -> Claims). */
export function navItemForPath(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
}

/** Where a role lands after sign-in when no `next` is given. */
export const HOME_PATH = "/claims";

/** Accepts only same-origin paths for post-login redirects. */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\") || next.startsWith("/login")) {
    return HOME_PATH;
  }
  return next;
}
