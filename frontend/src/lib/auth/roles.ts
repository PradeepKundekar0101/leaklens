export const ROLES = ["adjuster", "auditor", "manager", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const ROLE_LABELS: Record<Role, string> = {
  adjuster: "Adjuster",
  auditor: "Auditor",
  manager: "Manager",
  admin: "Admin",
};

export function isRole(value: string): value is Role {
  return (ROLES as readonly string[]).includes(value);
}

export function hasRole(role: string | undefined, allowed: readonly Role[]): boolean {
  return role !== undefined && isRole(role) && allowed.includes(role);
}
