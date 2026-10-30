import type { Metadata } from "next";
import { Suspense } from "react";

import { ProvidersTable } from "./providers-table";

export const metadata: Metadata = { title: "Providers" };

export default function ProvidersPage() {
  return (
    <Suspense>
      <ProvidersTable />
    </Suspense>
  );
}
