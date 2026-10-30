import type { Metadata } from "next";

import { NewClaim } from "./new-claim";

export const metadata: Metadata = { title: "New claim" };

export default function NewClaimPage() {
  return <NewClaim />;
}
