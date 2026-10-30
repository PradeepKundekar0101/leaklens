"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, ChevronLeft, Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AccessDenied } from "@/components/app-shell/states";
import { ParseStatusPill } from "@/components/claim-status";
import { Combobox } from "@/components/combobox";
import { PageHeader, Panel, PanelHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api/client";
import { getErrorMessage, unwrap } from "@/lib/api/errors";
import { useMe } from "@/lib/auth/hooks";
import { hasRole, ROLE_LABELS } from "@/lib/auth/roles";
import { useProcessClaim } from "@/lib/claims";
import { formatDate, formatINR } from "@/lib/format";
import { type MemberPolicyOption, useMemberPolicySearch, useProcedures, useProviders } from "@/lib/lookups";
import { DOC_TYPE_LABELS, humanize, roomLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

import { UploadBox } from "../[id]/documents-tab";
import { useClaim } from "../[id]/use-claim";

const ROOMS = ["general", "semi_private", "private", "deluxe"] as const;

export function NewClaim() {
  const { data: user } = useMe();
  const [claimId, setClaimId] = useState<string | null>(null);

  if (user && !hasRole(user.role, ["adjuster", "admin"])) {
    return <AccessDenied section="Creating claims" role={ROLE_LABELS[user.role]} />;
  }

  return (
    <div className="max-w-3xl">
      <Link
        href="/claims"
        className="-ml-1 mb-2 inline-flex items-center gap-0.5 rounded-sm px-1 text-[13px] font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="size-3.5" aria-hidden="true" />
        Claims
      </Link>
      <PageHeader title="New claim" description="Create a live claim, attach its bills and reports, then process it." />
      <ol className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]">
        <Step n={1} label="Claim details" state={claimId ? "done" : "current"} />
        <Step n={2} label="Documents" state={claimId ? "current" : "todo"} />
        <Step n={3} label="Process" state="todo" />
      </ol>
      {claimId ? <DocumentsStep claimId={claimId} /> : <DetailsStep onCreated={setClaimId} />}
    </div>
  );
}

function Step({ n, label, state }: { n: number; label: string; state: "done" | "current" | "todo" }) {
  return (
    <li className={cn("flex items-center gap-2", state === "todo" && "text-muted-foreground")} aria-current={state === "current" ? "step" : undefined}>
      <span
        className={cn(
          "num flex size-5 items-center justify-center rounded-full border text-xs font-semibold",
          state === "current" && "border-primary bg-primary text-primary-foreground",
          state === "done" && "border-primary text-primary",
        )}
      >
        {state === "done" ? <Check className="size-3" aria-hidden="true" /> : n}
      </span>
      <span className={cn(state === "current" && "font-semibold")}>{label}</span>
    </li>
  );
}

function DetailsStep({ onCreated }: { onCreated: (id: string) => void }) {
  const [form, setForm] = useState({
    member_policy_id: "",
    provider_id: "",
    procedure_code: "",
    diagnosis_code: "",
    admission_at: "",
    discharge_at: "",
    claim_type: "reimbursement" as "cashless" | "reimbursement",
    room_category: "semi_private",
    preauth_amount: "",
  });
  const [policyQuery, setPolicyQuery] = useState("");
  const [policy, setPolicy] = useState<MemberPolicyOption | null>(null);
  const policies = useMemberPolicySearch(policyQuery);
  const providers = useProviders();
  const procedures = useProcedures();
  const missing = !form.member_policy_id || !form.provider_id || !form.procedure_code;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const create = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/claims", {
          body: {
            member_policy_id: form.member_policy_id.trim(),
            provider_id: form.provider_id.trim(),
            procedure_code: form.procedure_code.trim(),
            diagnosis_code: form.diagnosis_code.trim(),
            admission_at: form.admission_at,
            discharge_at: form.discharge_at,
            claim_type: form.claim_type,
            room_category: form.room_category,
            preauth_amount: form.preauth_amount ? form.preauth_amount : null,
          },
        }),
      ) as { id: string; status: string },
    onSuccess: (res) => {
      toast.success(`Claim ${res.id} created`);
      onCreated(res.id);
    },
  });
  const datesBad = form.admission_at && form.discharge_at && form.discharge_at < form.admission_at;

  return (
    <Panel>
      <form
        className="grid gap-4 p-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!datesBad && !missing) create.mutate();
        }}
      >
        <Field
          id="member_policy_id"
          label="Member policy"
          hint={
            policy
              ? `${policy.product_id}, SI ${formatINR(policy.sum_insured)}, since ${formatDate(policy.start_date)}${policy.member_age ? `, member ${policy.member_age}` : ""}${policy.member_city ? `, ${policy.member_city}` : ""}`
              : "Search by policy ID (MP...) or member ID (M...)"
          }
        >
          <Combobox
            id="member_policy_id"
            className="w-full"
            value={form.member_policy_id}
            onChange={(v) => {
              setForm({ ...form, member_policy_id: v });
              setPolicy(policies.data?.find((p) => p.id === v) ?? null);
            }}
            onSearch={setPolicyQuery}
            loading={policies.isFetching && !policies.data}
            options={(policies.data ?? []).map((p) => ({
              value: p.id,
              label: p.id,
              hint: `${p.member_id}, ${p.product_id}, SI ${formatINR(p.sum_insured)}`,
            }))}
            selectedLabel={policy?.id}
            placeholder="Find a member policy"
            searchPlaceholder="Type 2+ characters of a policy or member ID"
            emptyText={policyQuery.trim().length < 2 ? "Type at least 2 characters." : "No policy matches."}
          />
        </Field>
        <Field id="provider_id" label="Provider">
          <Combobox
            id="provider_id"
            className="w-full"
            value={form.provider_id}
            onChange={(v) => setForm({ ...form, provider_id: v })}
            options={(providers.data ?? []).map((p) => ({ value: p.id, label: p.name, hint: `${p.city}, ${p.id}${p.network ? ", network" : ""}` }))}
            loading={providers.isPending}
            placeholder="Choose a provider"
            searchPlaceholder="Search provider, city or ID"
          />
        </Field>
        <Field id="procedure_code" label="Procedure">
          <Combobox
            id="procedure_code"
            className="w-full"
            value={form.procedure_code}
            onChange={(v) => {
              const proc = procedures.data?.find((p) => p.code === v);
              setForm({ ...form, procedure_code: v, diagnosis_code: proc?.icd10 ?? form.diagnosis_code });
            }}
            options={(procedures.data ?? []).map((p) => ({ value: p.code, label: p.name, hint: `${p.code}${p.icd10 ? `, ${p.icd10}` : ""}` }))}
            loading={procedures.isPending}
            placeholder="Choose a procedure"
            searchPlaceholder="Search procedure or code"
          />
        </Field>
        <Field id="diagnosis_code" label="Diagnosis code (ICD-10)" hint="Filled from the procedure. Change it if the diagnosis differs.">
          <Input id="diagnosis_code" value={form.diagnosis_code} onChange={set("diagnosis_code")} required className="num h-9" />
        </Field>
        <Field id="admission_at" label="Admitted on">
          <Input id="admission_at" type="date" value={form.admission_at} onChange={set("admission_at")} required className="num h-9" />
        </Field>
        <Field id="discharge_at" label="Discharged on" error={datesBad ? "Discharge must be on or after admission." : undefined}>
          <Input
            id="discharge_at"
            type="date"
            value={form.discharge_at}
            min={form.admission_at || undefined}
            onChange={set("discharge_at")}
            required
            aria-invalid={!!datesBad}
            className="num h-9"
          />
        </Field>
        <Field id="claim_type" label="Claim type">
          <Select value={form.claim_type} onValueChange={(v) => setForm({ ...form, claim_type: v as typeof form.claim_type })}>
            <SelectTrigger id="claim_type" className="h-9 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="reimbursement">Reimbursement</SelectItem>
              <SelectItem value="cashless">Cashless</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field id="room_category" label="Room category">
          <Select value={form.room_category} onValueChange={(v) => setForm({ ...form, room_category: v })}>
            <SelectTrigger id="room_category" className="h-9 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROOMS.map((r) => (
                <SelectItem key={r} value={r}>
                  {roomLabel(r)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field
          id="preauth_amount"
          label="Pre-auth amount (optional)"
          hint={form.preauth_amount ? formatINR(form.preauth_amount) : "Leave empty if there was no pre-authorisation"}
        >
          <Input
            id="preauth_amount"
            inputMode="decimal"
            value={form.preauth_amount}
            onChange={(e) => setForm({ ...form, preauth_amount: e.target.value.replace(/[^\d.]/g, "") })}
            className="num h-9"
          />
        </Field>
        {create.isError && (
          <p className="text-[13px] text-destructive sm:col-span-2" role="alert">
            {getErrorMessage(create.error)}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t pt-4 sm:col-span-2">
          <Button asChild variant="outline">
            <Link href="/claims">Cancel</Link>
          </Button>
          <Button type="submit" disabled={create.isPending || missing}>
            {create.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
            Create claim
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {(error || hint) && <p className={cn("text-xs", error ? "text-destructive" : "text-muted-foreground")}>{error ?? hint}</p>}
    </div>
  );
}

function DocumentsStep({ claimId }: { claimId: string }) {
  const claim = useClaim(claimId);
  const router = useRouter();
  const process = useProcessClaim();
  const docs = claim.data?.documents ?? [];
  const parsing = docs.some((d) => d.parse_status === "pending" || d.parse_status === "parsing");

  return (
    <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_16rem]">
      <Panel>
        <PanelHeader title={`Documents for ${claimId}`} description="Upload the final bill, discharge summary and any prescriptions or pre-auth letters." />
        {docs.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">No documents yet.</p>
        ) : (
          <ul className="divide-y">
            {docs.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-[13px]">
                <span className="min-w-0 truncate font-medium">{d.filename || `Document ${d.id}`}</span>
                <span className="flex items-center gap-2 text-xs text-muted-foreground">
                  {DOC_TYPE_LABELS[d.doc_type] ?? humanize(d.doc_type)}
                  <ParseStatusPill status={d.parse_status} />
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center justify-end gap-2 border-t px-4 py-3">
          {parsing && <span className="mr-auto text-xs text-muted-foreground">Wait for parsing to finish before processing.</span>}
          <Button asChild variant="outline">
            <Link href={`/claims/${encodeURIComponent(claimId)}`}>Open claim</Link>
          </Button>
          <Button
            disabled={docs.length === 0 || parsing || process.isPending}
            onClick={() =>
              process.mutate(claimId, {
                onSuccess: () => {
                  toast.success("Processing started");
                  router.push(`/claims/${encodeURIComponent(claimId)}`);
                },
                onError: (e) => toast.error(getErrorMessage(e)),
              })
            }
          >
            {process.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play data-icon="inline-start" aria-hidden="true" />}
            Process claim
          </Button>
        </div>
      </Panel>
      <UploadBox claimId={claimId} />
    </div>
  );
}
