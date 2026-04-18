"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Loader2, Plus, Search, Sparkles, Trash2, User } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { ChatHistoryItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SUGGESTIONS = [
  "Show books with optimistic tone and strong ratings.",
  "Find memoir-style books about resilience.",
  "Recommend books similar to mystery-driven narratives."
];

interface ChatTurn {
  id: string;
  question: string;
  answer: string;
  sources: string[];
}

function extractSourceLabels(rawSources: unknown[]): string[] {
  const labels: string[] = [];
  for (const source of rawSources) {
    if (typeof source === "string") {
      labels.push(source);
      continue;
    }
    if (source && typeof source === "object" && "title" in source) {
      const title = String((source as { title?: unknown }).title ?? "").trim();
      if (title) {
        labels.push(title);
      }
    }
  }
  return Array.from(new Set(labels)).slice(0, 6);
}

export default function QAPage() {
  const [question, setQuestion] = useState<string>("");
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const questionInputRef = useRef<HTMLInputElement | null>(null);

  const historyQuery = useQuery({
    queryKey: ["qa-history"],
    queryFn: api.getHistory
  });

  const askMutation = useMutation({
    mutationFn: (prompt: string) => api.askQuestion(prompt),
    onSuccess: (data) => {
      toast.success("Answer generated.");
      setChatTurns((prev) => [
        ...prev,
        {
          id: String(data.chat_id),
          question: String(askMutation.variables ?? ""),
          answer: data.answer,
          sources: data.sources
        }
      ]);
      setQuestion("");
      historyQuery.refetch();
    },
    onError: (err: Error) => toast.error(err.message)
  });

  const clearMutation = useMutation({
    mutationFn: api.clearHistory,
    onSuccess: (data) => {
      toast.success(`Deleted ${data.deleted_count} history entries.`);
      setChatTurns([]);
      setConfirmDeleteOpen(false);
      historyQuery.refetch();
    },
    onError: (err: Error) => toast.error(err.message)
  });

  const recentItems = useMemo(() => {
    return [...(historyQuery.data ?? [])].slice(0, 16);
  }, [historyQuery.data]);

  const normalizedSearchTerm = searchTerm.trim().toLowerCase();

  const filteredChatTurns = useMemo(() => {
    if (!normalizedSearchTerm) {
      return chatTurns;
    }
    return chatTurns.filter((turn) => {
      const sourceText = turn.sources.join(" ").toLowerCase();
      return (
        turn.question.toLowerCase().includes(normalizedSearchTerm) ||
        turn.answer.toLowerCase().includes(normalizedSearchTerm) ||
        sourceText.includes(normalizedSearchTerm)
      );
    });
  }, [chatTurns, normalizedSearchTerm]);

  const filteredRecentItems = useMemo(() => {
    if (!normalizedSearchTerm) {
      return recentItems;
    }
    return recentItems.filter((row) => {
      const sources = Array.isArray(row.sources) ? row.sources.map((source) => String(source)).join(" ").toLowerCase() : "";
      return (
        row.question.toLowerCase().includes(normalizedSearchTerm) ||
        row.answer.toLowerCase().includes(normalizedSearchTerm) ||
        sources.includes(normalizedSearchTerm)
      );
    });
  }, [recentItems, normalizedSearchTerm]);

  const handleNewChat = () => {
    setChatTurns([]);
    setQuestion("");
    setSearchTerm("");
    askMutation.reset();
    questionInputRef.current?.focus();
  };

  const latestUserPrompt = askMutation.variables ?? "";

  return (
    <div className="grid gap-6 lg:grid-cols-[1.7fr_1fr]">
      <Card className="glass h-[calc(100vh-7.5rem)] min-h-[560px] overflow-hidden">
        <CardHeader className="border-b border-[#8ec8ff2f] bg-[#86ccff12]">
          <div className="space-y-3">
            <CardTitle className="flex items-center gap-2 text-[#dff2ff]">
              <Sparkles className="h-5 w-5 text-[#8fd9ff]" /> Premium RAG Chat
            </CardTitle>
            <p className="mt-1 text-sm text-[#aac6dd]">Grounded answers from indexed book chunks with visible sources.</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8eb2cd]" />
                <Input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search in chat and recent sessions..."
                  className="h-9 border-[#8ec8ff4d] bg-[#0a1e33a6] pl-9 text-[#e5f4ff] placeholder:text-[#8eb2cd]"
                />
              </div>
              <Button variant="outline" className="h-9 border-[#8ec8ff4d]" onClick={handleNewChat}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                New Chat
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex h-full min-h-0 flex-col gap-4 p-4">
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((item) => (
              <button
                key={item}
                type="button"
                className="rounded-full border border-[#8ec8ff44] bg-[#8ec8ff1f] px-3 py-1 text-xs text-[#cbe6ff] transition hover:border-[#b8e7ff99] hover:bg-[#8ec8ff2f]"
                onClick={() => setQuestion(item)}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="premium-scroll min-h-0 flex-1 space-y-4 overflow-y-auto rounded-2xl border border-[#8ec8ff33] bg-[#081a2e99] p-4">
            {filteredChatTurns.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#8ec8ff3f] bg-[#8ec8ff10] p-5 text-sm text-[#aac6dd]">
                {normalizedSearchTerm ? "No matching chat content found for your search." : "Start a new conversation by typing your question below."}
              </div>
            ) : null}

            {filteredChatTurns.map((row) => (
              <div key={row.id} className="space-y-3">
                <div className="ml-auto flex max-w-[85%] justify-end gap-2">
                  <div className="rounded-2xl rounded-br-sm border border-[#9ad5ff66] bg-[#7fbfff2a] px-4 py-3 text-sm text-[#e4f5ff]">
                    {row.question}
                  </div>
                  <div className="mt-1 rounded-full bg-[#8ccfff2b] p-2 text-[#a5dcff]"><User className="h-4 w-4" /></div>
                </div>

                <div className="mr-auto flex max-w-[88%] gap-2">
                  <div className="mt-1 rounded-full bg-[#8ccfff2b] p-2 text-[#a5dcff]"><Bot className="h-4 w-4" /></div>
                  <div className="rounded-2xl rounded-bl-sm border border-[#8ec8ff4f] bg-[#8ccfff1a] px-4 py-3 text-sm leading-relaxed text-[#d7ecff]">
                    <p className="whitespace-pre-wrap">{row.answer}</p>
                    {row.sources.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {row.sources.map((label) => (
                          <span key={`${row.id}-${label}`} className="rounded-full border border-[#8ec8ff55] bg-[#8ec8ff1f] px-2.5 py-1 text-[11px] text-[#cbe6ff]">
                            {label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}

            {askMutation.isPending ? (
              <div className="space-y-3">
                {latestUserPrompt ? (
                  <div className="ml-auto flex max-w-[85%] justify-end gap-2">
                    <div className="rounded-2xl rounded-br-sm border border-[#9ad5ff66] bg-[#7fbfff2a] px-4 py-3 text-sm text-[#e4f5ff]">
                      {latestUserPrompt}
                    </div>
                    <div className="mt-1 rounded-full bg-[#8ccfff2b] p-2 text-[#a5dcff]"><User className="h-4 w-4" /></div>
                  </div>
                ) : null}
                <div className="mr-auto flex max-w-[70%] gap-2">
                  <div className="mt-1 rounded-full bg-[#8ccfff2b] p-2 text-[#a5dcff]"><Bot className="h-4 w-4" /></div>
                  <div className="rounded-2xl rounded-bl-sm border border-[#8ec8ff4f] bg-[#8ccfff1a] px-4 py-3 text-sm text-[#d7ecff]">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="sticky bottom-0 rounded-xl border border-[#8ec8ff33] bg-[#86ccff12] p-3">
            <div className="flex gap-2">
              <Input
                ref={questionInputRef}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a grounded question from your indexed books..."
                className="border-[#8ec8ff4d] bg-[#0a1e33a6] text-[#e5f4ff] placeholder:text-[#8eb2cd]"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && question.trim().length > 0 && !askMutation.isPending) {
                    event.preventDefault();
                    askMutation.mutate(question.trim());
                  }
                }}
              />
              <Button
                className="bg-[#8fd4ff] text-[#082139] hover:bg-[#a8e0ff]"
                disabled={askMutation.isPending || question.trim().length === 0}
                onClick={() => askMutation.mutate(question.trim())}
              >
                {askMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Ask
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="glass h-fit">
        <CardHeader className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-[#dff2ff]">Recent Sessions</CardTitle>
          </div>
          <div>
            <Button
              variant="outline"
              className="h-8 w-full border-[#ef7aa87a] text-xs text-[#ffb8ce] hover:bg-[#ef7aa81f]"
              onClick={() => setConfirmDeleteOpen((prev) => !prev)}
              disabled={(historyQuery.data?.length ?? 0) === 0 || clearMutation.isPending}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete All History
            </Button>
            {confirmDeleteOpen ? (
              <div className="mt-2 rounded-lg border border-[#ef7aa85e] bg-[#ef7aa817] p-2">
                <p className="text-xs text-[#ffd1de]">Are you sure? This will permanently delete all chat history.</p>
                <div className="mt-2 flex gap-2">
                  <Button
                    variant="outline"
                    className="h-7 flex-1 text-xs"
                    onClick={() => setConfirmDeleteOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    className="h-7 flex-1 bg-[#ff9ab9] text-xs text-[#3b0f1e] hover:bg-[#ffb1c8]"
                    onClick={() => clearMutation.mutate()}
                    disabled={clearMutation.isPending}
                  >
                    {clearMutation.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                    Confirm
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {historyQuery.isLoading ? <p className="text-sm text-[#aac6dd]">Loading history...</p> : null}
          {historyQuery.isError ? <p className="text-sm text-danger">{(historyQuery.error as Error).message}</p> : null}
          {filteredRecentItems.map((row: ChatHistoryItem) => (
            <button
              key={row.id}
              type="button"
              className="w-full rounded-xl border border-[#8ec8ff38] bg-[#8ec8ff14] p-3 text-left transition hover:border-[#b8e7ff88] hover:bg-[#8ec8ff24]"
              onClick={() => {
                setChatTurns([
                  {
                    id: String(row.id),
                    question: row.question,
                    answer: row.answer,
                    sources: extractSourceLabels(row.sources)
                  }
                ]);
              }}
            >
              <p className="line-clamp-2 text-xs font-medium text-[#d5ebff]">{row.question}</p>
              <p className="mt-1 line-clamp-2 text-xs text-[#9fbdd6]">{row.answer}</p>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}


