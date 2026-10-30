import { StatusPill } from "@/components/status-badges";
import { CLAIM_STATUS_META, type ClaimStatus, humanize, PARSE_STATUS_META } from "@/lib/labels";

export function ClaimStatusPill({ status }: { status: string }) {
  const meta = CLAIM_STATUS_META[status as ClaimStatus];
  return <StatusPill label={meta?.label ?? humanize(status)} tone={meta?.tone} />;
}

export function ParseStatusPill({ status }: { status: string }) {
  const meta = PARSE_STATUS_META[status];
  return <StatusPill label={meta?.label ?? humanize(status)} tone={meta?.tone} />;
}

const JOB_TONES: Record<string, string | undefined> = {
  queued: undefined,
  running: "--primary",
  done: "--action-approve",
  failed: "--destructive",
};

export function JobStatusPill({ status }: { status: string }) {
  return <StatusPill label={humanize(status)} tone={JOB_TONES[status]} />;
}
