import { Sparkles } from "lucide-react";

import { Panel, PanelHeader } from "@/components/page";
import type { ClaimDetail } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

export function RecommendationCard({ claim }: { claim: ClaimDetail }) {
  const rec = claim.recommendation;
  if (!rec) {
    return (
      <Panel>
        <PanelHeader title="Recommendation" />
        <p className="px-4 py-4 text-[13px] text-muted-foreground">
          {claim.status === "processing"
            ? "LeakLens is checking this claim. The recommendation appears here when it finishes."
            : claim.status === "failed"
              ? "Processing failed. Process the claim again, or check the Audit tab for the error."
              : "This claim has not been processed yet. Process it to get a recommendation."}
        </p>
      </Panel>
    );
  }
  return (
    <Panel>
      <PanelHeader
        title="Recommendation"
        actions={
          <span
            className="inline-flex items-center gap-1 text-xs text-muted-foreground"
            title={rec.explanation_source === "llm" ? "Written by the language model, numbers checked" : "Generated from a template"}
          >
            {rec.explanation_source === "llm" && <Sparkles className="size-3" aria-hidden="true" />}
            {rec.explanation_source === "llm" ? "Model explanation" : "Template explanation"}
          </span>
        }
      />
      <div className="space-y-3 px-4 py-3">
        <p className="text-[13px] leading-5 whitespace-pre-line">{rec.explanation}</p>
        {rec.key_findings.length > 0 && (
          <div>
            <h3 className="mb-1 text-xs font-semibold text-muted-foreground">Key findings</h3>
            <ul className="list-disc space-y-1 pl-4 text-[13px] leading-5 marker:text-muted-foreground">
              {rec.key_findings.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Recommended {formatDateTime(rec.created_at)}</p>
      </div>
    </Panel>
  );
}
