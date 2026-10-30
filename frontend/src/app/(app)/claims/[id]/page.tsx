import type { Metadata } from "next";

import { ClaimReview } from "./claim-review";

export const metadata: Metadata = { title: "Claim review" };

export default function ClaimReviewPage() {
  return <ClaimReview />;
}
