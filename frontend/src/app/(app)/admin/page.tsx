import type { Metadata } from "next";

import { Admin } from "./admin";

export const metadata: Metadata = { title: "Admin" };

export default function AdminPage() {
  return <Admin />;
}
