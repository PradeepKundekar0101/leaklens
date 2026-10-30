import { CircleAlert } from "lucide-react";

import { Panel, PanelHeader } from "@/components/page";
import { ActionBadge, isClaimAction, ToneBadge } from "@/components/status-badges";
import type { InvestigationReport } from "@/lib/api/types";
import { humanize } from "@/lib/labels";

export function InvestigationTab({ report }: { report: InvestigationReport }) {
  const dropped = Array.isArray(report.dropped_unsupported_findings) ? report.dropped_unsupported_findings.length : 0;
  const tools = Array.isArray(report.tools_used) ? (report.tools_used as string[]) : [];
  return (
    <div className="space-y-4">
      {report.incomplete && (
        <p className="flex items-start gap-2 rounded-md border border-action-investigate/30 bg-action-investigate/8 px-3 py-2 text-[13px] text-action-investigate">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          The investigation stopped before it finished (tool budget or model limit). Treat it as partial.
        </p>
      )}
      <Panel>
        <PanelHeader
          title="Investigator summary"
          actions={
            isClaimAction(report.suggested_action) && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                Suggests <ActionBadge action={report.suggested_action} />
              </span>
            )
          }
        />
        <p className="px-4 py-3 text-[13px] leading-5 whitespace-pre-line">{report.summary}</p>
        {tools.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-t px-4 py-2.5 text-xs text-muted-foreground">
            Tools used
            {tools.map((t) => (
              <ToneBadge key={t} className="font-medium">
                {humanize(t)}
              </ToneBadge>
            ))}
          </div>
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title="Findings"
          description={
            dropped > 0
              ? `Each finding cites the tool result it rests on. ${dropped} unsupported ${dropped === 1 ? "finding was" : "findings were"} removed.`
              : "Each finding cites the tool result it rests on."
          }
        />
        {report.findings.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted-foreground">No supported findings.</p>
        ) : (
          <ol className="divide-y">
            {report.findings.map((f, i) => (
              <li key={i} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-2 px-4 py-3 text-[13px]">
                <span className="num text-muted-foreground">{i + 1}</span>
                <div>
                  <p className="font-medium">{f.statement}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <span className="font-semibold">{humanize(f.evidence_tool)}</span>: {f.evidence}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Panel>

      {report.open_questions && report.open_questions.length > 0 && (
        <Panel>
          <PanelHeader title="Open questions" />
          <ul className="list-disc space-y-1 py-3 pr-4 pl-8 text-[13px] marker:text-muted-foreground">
            {report.open_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
