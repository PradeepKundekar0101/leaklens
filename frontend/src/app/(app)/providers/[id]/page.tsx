import type { Metadata } from "next";

import { ProviderProfile } from "./provider-profile";

export const metadata: Metadata = { title: "Provider" };

export default function ProviderPage() {
  return <ProviderProfile />;
}
