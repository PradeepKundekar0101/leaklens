"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Loader2, Wrench } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage, toApiError } from "@/lib/api/errors";
import { apiRequest } from "@/lib/api/http";
import type { CopilotMessage } from "@/lib/api/types";
import { humanize } from "@/lib/labels";
import { createSseParser } from "@/lib/sse";
import { cn } from "@/lib/utils";

interface ChatMessage extends CopilotMessage {
  tools?: string[];
  error?: string;
  streaming?: boolean;
}

export function CopilotDrawer({ claimId, open, onOpenChange }: { claimId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const history = useQuery({
    queryKey: ["copilot", claimId],
    queryFn: () => apiRequest<{ messages: CopilotMessage[]; suggested: string[] }>(`/api/v1/claims/${encodeURIComponent(claimId)}/copilot`),
    enabled: open,
    staleTime: Infinity,
  });
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const shown = useMemo(() => messages ?? history.data?.messages ?? [], [messages, history.data]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [shown]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setDraft("");
    setBusy(true);
    const base: ChatMessage[] = [...shown, { role: "user", content: message }, { role: "assistant", content: "", tools: [], streaming: true }];
    setMessages(base);
    const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => {
        const list = [...(prev ?? base)];
        list[list.length - 1] = fn(list[list.length - 1]);
        return list;
      });

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await fetch(`/api/v1/claims/${encodeURIComponent(claimId)}/copilot`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => null);
        throw toApiError(body, response);
      }
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      const parse = createSseParser();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const ev of parse(value)) {
          let data: { delta?: string; name?: string; message?: string } = {};
          try {
            data = JSON.parse(ev.data);
          } catch {
            continue;
          }
          if (ev.event === "text" && data.delta) patchLast((m) => ({ ...m, content: m.content + data.delta }));
          else if (ev.event === "tool" && data.name) patchLast((m) => ({ ...m, tools: [...(m.tools ?? []), data.name!] }));
          else if (ev.event === "error") patchLast((m) => ({ ...m, error: data.message ?? "The copilot hit an error." }));
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) patchLast((m) => ({ ...m, error: getErrorMessage(e) }));
    } finally {
      patchLast((m) => ({ ...m, streaming: false }));
      setBusy(false);
      void queryClient.invalidateQueries({ queryKey: ["claim-audit", claimId] });
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle>Copilot</SheetTitle>
          <SheetDescription>Ask about claim {claimId}. Answers cite the stored analysis and read-only tools.</SheetDescription>
        </SheetHeader>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
          {history.isPending && open ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-3/4" />
              <Skeleton className="ml-auto h-8 w-1/2" />
            </div>
          ) : history.isError ? (
            <p className="text-[13px] text-destructive">{getErrorMessage(history.error)}</p>
          ) : shown.length === 0 ? (
            <div className="space-y-2">
              <p className="text-[13px] text-muted-foreground">Start with a question:</p>
              <div className="flex flex-col items-start gap-1.5">
                {(history.data?.suggested ?? []).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void send(s)}
                    className="rounded-md border bg-card px-2.5 py-1.5 text-left text-[13px] outline-none hover:border-primary/40 hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            shown.map((m, i) => <Bubble key={i} message={m} />)
          )}
        </div>

        <form
          className="border-t p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send(draft);
          }}
        >
          <div className="relative">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send(draft);
                }
              }}
              rows={2}
              maxLength={4000}
              placeholder="Ask a question"
              aria-label="Message the copilot"
              className="resize-none pr-11"
            />
            <Button type="submit" size="icon-sm" className="absolute right-2 bottom-2" disabled={busy || !draft.trim()} aria-label="Send">
              {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : <ArrowUp aria-hidden="true" />}
            </Button>
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">Enter to send, Shift+Enter for a new line.</p>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function Bubble({ message: m }: { message: ChatMessage }) {
  if (m.role === "user") {
    return (
      <div className="ml-auto w-fit max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3 py-2 text-[13px] whitespace-pre-line text-primary-foreground">
        {m.content}
      </div>
    );
  }
  return (
    <div className="max-w-[95%] space-y-1.5">
      {m.tools && m.tools.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {m.tools.map((t, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-[4px] bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              <Wrench className="size-3" aria-hidden="true" />
              {humanize(t)}
            </span>
          ))}
        </div>
      )}
      <div className={cn("rounded-lg rounded-bl-sm border bg-card px-3 py-2 text-[13px] leading-5", !m.content && m.streaming && "w-fit")}>
        {m.content ? <RichText text={m.content} /> : m.streaming ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-label="Thinking" /> : null}
        {m.error && <p className="mt-1 text-xs text-destructive">{m.error}</p>}
      </div>
    </div>
  );
}

/** Minimal markdown: paragraphs, "-" bullets and **bold**. */
export function RichText({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="space-y-2">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*[-*]\s+/.test(l) || !l.trim())) {
          return (
            <ul key={i} className="list-disc space-y-0.5 pl-4 marker:text-muted-foreground">
              {lines.filter((l) => l.trim()).map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="whitespace-pre-line">
            {inline(block)}
          </p>
        );
      })}
    </div>
  );
}

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  );
}
