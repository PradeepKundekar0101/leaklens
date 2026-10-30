import type { Metadata } from "next";

import { Policies } from "./policies";

export const metadata: Metadata = { title: "Policies" };

export default function PoliciesPage() {
  return <Policies />;
}
