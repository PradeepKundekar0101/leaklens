import type { Metadata } from "next";
import { Suspense } from "react";

import { ClaimsQueue } from "./claims-queue";

export const metadata: Metadata = { title: "Claims" };

export default function ClaimsPage() {
  return (
    <Suspense>
      <ClaimsQueue />
    </Suspense>
  );
}
