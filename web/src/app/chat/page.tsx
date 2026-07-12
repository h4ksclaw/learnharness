"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { apiClient, type Agent, type ChatMessage, type ChatResponse } from "@/lib/api";
import {
  Send,
  Hash,
  Plus,
  CornerDownRight,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Loader2,
} from "lucide-react";

interface Thread {
  id: string;
  title: string;
  messages: ChatMessage[];
  parentId: string | null;
  deltas: ChatResponse["mastery_deltas"];
  corrections: ChatResponse["corrections"];
}

export default function ChatPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [learnerId, setLearnerId] = useState<string>("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<string>("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [showNewThread, setShowNewThread] = useState(false);
  const [newThreadTitle, setNewThreadTitle] = useState("");
  const [newThreadParent, setNewThreadParent] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiClient.listAgents().then((data) => {
      setAgents(data);
      // FIX: don't call setSelectedAgent during render — do it in the effect
      if (data.length > 0 && !selectedAgent) {
        setSelectedAgent(data[0].id);
      }
    }).catch(() => setAgents([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Restore session
  useEffect(() => {
    const saved = localStorage.getItem("lh_session");
    if (saved) {
      try {
        const s = JSON.parse(saved);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (s.learnerId) setLearnerId(s.learnerId);
        if (s.threads) setThreads(s.threads);
        if (s.activeThread) setActiveThread(s.activeThread);
        if (s.selectedAgent) setSelectedAgent(s.selectedAgent);
      } catch {
        // ignore corrupt session
      }
    }
  }, []);

  // Persist session
  useEffect(() => {
    localStorage.setItem(
      "lh_session",
      JSON.stringify({ learnerId, threads, activeThread, selectedAgent }),
    );
  }, [learnerId, threads, activeThread, selectedAgent]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threads, activeThread]);

  const ensureLearner = useCallback(async () => {
    if (learnerId || !selectedAgent) return learnerId;
    try {
      const learner = await apiClient.createLearner(selectedAgent, "Web User");
      setLearnerId(learner.id);
      return learner.id;
    } catch {
      return null;
    }
  }, [learnerId, selectedAgent]);

  const createThread = (title: string, parentId: string | null = null) => {
    const id = `thread_${Date.now()}`;
    const thread: Thread = {
      id,
      title,
      messages: [],
      parentId,
      deltas: [],
      corrections: [],
    };
    setThreads((prev) => [...prev, thread]);
    setActiveThread(id);
    setShowNewThread(false);
    setNewThreadTitle("");
    setNewThreadParent(null);
    return id;
  };

  const openNewThreadModal = (parentId: string | null = null) => {
    setNewThreadParent(parentId);
    if (parentId) {
      const parent = threads.find((t) => t.id === parentId);
      setNewThreadTitle(parent ? `Re: ${parent.title}` : "");
    } else {
      setNewThreadTitle("");
    }
    setShowNewThread(true);
  };

  const sendMessage = async () => {
    if (!input.trim() || !selectedAgent) return;
    const lid = await ensureLearner();
    if (!lid) return;

    const thread = threads.find((t) => t.id === activeThread);
    if (!thread) return;

    const userMsg: ChatMessage = { role: "user", content: input };
    const newMessages = [...thread.messages, userMsg];
    setSending(true);
    setInput("");

    // Optimistic update
    setThreads((prev) =>
      prev.map((t) =>
        t.id === activeThread ? { ...t, messages: newMessages } : t,
      ),
    );

    try {
      const resp = await apiClient.chat(
        selectedAgent,
        lid,
        newMessages,
        activeThread,
      );

      const aiMsg: ChatMessage = {
        role: "assistant",
        content: resp.choices[0]?.message?.content || "",
      };

      setThreads((prev) =>
        prev.map((t) =>
          t.id === activeThread
            ? {
                ...t,
                messages: [...newMessages, aiMsg],
                deltas: resp.mastery_deltas || [],
                corrections: resp.corrections || [],
              }
            : t,
        ),
      );
    } catch (e) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `⚠️ Error: ${e instanceof Error ? e.message : "Failed to send"}`,
      };
      setThreads((prev) =>
        prev.map((t) =>
          t.id === activeThread
            ? { ...t, messages: [...newMessages, errorMsg] }
            : t,
        ),
      );
    }
    setSending(false);
  };

  const currentThread = threads.find((t) => t.id === activeThread);
  const topLevelThreads = threads.filter((t) => t.parentId === null);

  return (
    <div className="flex h-full">
      {/* Threads sidebar */}
      <div className="flex w-60 flex-col border-r border-white/[0.05] bg-[#0f1011]">
        <div className="flex h-14 items-center justify-between px-4">
          <span className="text-sm font-semibold text-[#f7f8f8]">Threads</span>
          <button
            onClick={() => openNewThreadModal(null)}
            className="rounded p-1 text-[#8a8f98] hover:bg-white/[0.06] hover:text-[#f7f8f8]"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Agent selector */}
        <div className="px-3 pb-2">
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="w-full rounded-md border border-white/[0.08] bg-[#191a1b] px-2 py-1.5 text-xs text-[#d0d6e0] focus:border-[#10b981] focus:outline-none"
          >
            <option value="">Select agent...</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto px-2">
          {topLevelThreads.length === 0 ? (
            <p className="px-2 py-4 text-xs text-[#62666d]">
              No threads yet. Click + to start.
            </p>
          ) : (
            topLevelThreads.map((t) => {
              const subs = threads.filter(
                (st) => st.parentId === t.id,
              );
              return (
                <div key={t.id} className="mb-1">
                  <button
                    onClick={() => setActiveThread(t.id)}
                    className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                      activeThread === t.id
                        ? "bg-[#191a1b] text-[#f7f8f8]"
                        : "text-[#8a8f98] hover:bg-white/[0.03] hover:text-[#d0d6e0]"
                    }`}
                  >
                    <Hash className="h-3 w-3 shrink-0" />
                    <span className="truncate">{t.title}</span>
                  </button>
                  {/* Subthreads */}
                  {subs.map((st) => (
                    <button
                      key={st.id}
                      onClick={() => setActiveThread(st.id)}
                      className={`flex w-full items-center gap-1.5 rounded-md py-1.5 pl-6 pr-2 text-left text-xs transition-colors ${
                        activeThread === st.id
                          ? "bg-[#191a1b] text-[#f7f8f8]"
                          : "text-[#62666d] hover:bg-white/[0.03] hover:text-[#d0d6e0]"
                      }`}
                    >
                      <CornerDownRight className="h-3 w-3 shrink-0" />
                      <span className="truncate">{st.title}</span>
                    </button>
                  ))}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {currentThread ? (
          <>
            {/* Thread header */}
            <div className="flex h-14 items-center justify-between border-b border-white/[0.05] px-6">
              <div className="flex items-center gap-2">
                <Hash className="h-4 w-4 text-[#8a8f98]" />
                <span className="font-semibold text-[#f7f8f8]">{currentThread.title}</span>
                {currentThread.messages.length > 0 && (
                  <span className="text-xs text-[#62666d]">
                    {currentThread.messages.length} messages
                  </span>
                )}
              </div>
              <button
                onClick={() => openNewThreadModal(currentThread.id)}
                className="flex items-center gap-1 rounded-md px-3 py-1.5 text-xs text-[#8a8f98] hover:bg-white/[0.06] hover:text-[#f7f8f8]"
              >
                <CornerDownRight className="h-3 w-3" />
                New subthread
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {currentThread.messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <p className="text-sm text-[#62666d]">
                    Send a message to start learning
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {currentThread.messages.map((msg, i) => (
                    <MessageBubble
                      key={i}
                      message={msg}
                      corrections={
                        msg.role === "assistant" && i === currentThread.messages.length - 1
                          ? currentThread.corrections
                          : []
                      }
                      deltas={
                        msg.role === "assistant" && i === currentThread.messages.length - 1
                          ? currentThread.deltas
                          : []
                      }
                    />
                  ))}
                  {/* Typing indicator */}
                  {sending && (
                    <div className="flex justify-start">
                      <div className="flex items-center gap-2 rounded-2xl border border-white/[0.08] bg-[#191a1b] px-4 py-3">
                        <Loader2 className="h-4 w-4 animate-spin text-[#8a8f98]" />
                        <span className="text-sm text-[#8a8f98]">
                          Agent is thinking...
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t border-white/[0.05] bg-[#0f1011] p-4">
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder={
                    selectedAgent
                      ? "Type a message..."
                      : "Select an agent first"
                  }
                  disabled={!selectedAgent || sending}
                  rows={1}
                  className="flex-1 resize-none rounded-xl border border-white/[0.08] bg-[#08090a] px-4 py-2.5 text-sm text-[#f7f8f8] placeholder-[#62666d] focus:border-[#10b981] focus:outline-none disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || sending || !selectedAgent}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#10b981] text-white hover:bg-[#34d399] disabled:opacity-30"
                >
                  {sending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center text-center">
            <p className="text-sm text-[#62666d]">
              Create a thread to start chatting
            </p>
            <button
              onClick={() => openNewThreadModal(null)}
              className="mt-3 flex items-center gap-2 rounded-md bg-[#10b981] px-4 py-2 text-sm font-medium text-white hover:bg-[#34d399]"
            >
              <Plus className="h-4 w-4" />
              New Thread
            </button>
          </div>
        )}
      </div>

      {/* New thread modal */}
      {showNewThread && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setShowNewThread(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#191a1b] p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-3 text-lg font-semibold text-[#f7f8f8]">
              {newThreadParent ? "New Subthread" : "New Thread"}
            </h2>
            <input
              value={newThreadTitle}
              onChange={(e) => setNewThreadTitle(e.target.value)}
              placeholder="e.g. German grammar practice"
              onKeyDown={(e) => {
                if (e.key === "Enter" && newThreadTitle.trim()) {
                  createThread(newThreadTitle, newThreadParent);
                }
              }}
              autoFocus
              className="w-full rounded-md border border-white/[0.08] bg-[#0f1011] px-3 py-2 text-sm text-[#f7f8f8] placeholder-[#62666d] focus:border-[#10b981] focus:outline-none"
            />
            <div className="mt-4 flex justify-end gap-3">
              <button
                onClick={() => setShowNewThread(false)}
                className="rounded-md px-4 py-2 text-sm text-[#8a8f98] hover:text-[#f7f8f8]"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  newThreadTitle.trim() &&
                  createThread(newThreadTitle, newThreadParent)
                }
                disabled={!newThreadTitle.trim()}
                className="rounded-md bg-[#10b981] px-4 py-2 text-sm font-medium text-white hover:bg-[#34d399] disabled:opacity-40"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({
  message,
  corrections,
  deltas,
}: {
  message: ChatMessage;
  corrections: ChatResponse["corrections"];
  deltas: ChatResponse["mastery_deltas"];
}) {
  const isUser = message.role === "user";
  const isError = message.content.startsWith("⚠️");

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[70%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm ${
            isError
              ? "bg-red-900/30 text-red-300"
              : isUser
                ? "bg-emerald-600 text-white"
                : "border border-white/[0.08] bg-[#191a1b] text-[#f7f8f8]"
          }`}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Corrections */}
        {corrections.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {corrections.map((c, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border border-amber-800/30 bg-amber-900/10 px-3 py-2 text-xs"
              >
                <AlertCircle
                  className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                    c.severity === "error" ? "text-red-400" : "text-amber-400"
                  }`}
                />
                <div>
                  <span className="text-[#62666d] line-through">
                    {c.original}
                  </span>
                  <span className="mx-1 text-[#62666d]">→</span>
                  <span className="text-[#10b981]">{c.corrected}</span>
                  {c.rule && (
                    <span className="block text-[#8a8f98]">{c.rule}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Mastery deltas */}
        {deltas.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {deltas.map((d, i) => (
              <span
                key={i}
                className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                  d.direction === "up"
                    ? "bg-[#10b981]/10 text-[#10b981]"
                    : d.direction === "down"
                      ? "bg-red-900/30 text-red-400"
                      : "bg-white/[0.06] text-[#8a8f98]"
                }`}
              >
                {d.direction === "up" ? (
                  <TrendingUp className="h-3 w-3" />
                ) : d.direction === "down" ? (
                  <TrendingDown className="h-3 w-3" />
                ) : null}
                {d.concept_name}: {Math.round(d.before * 100)}%
                {" → "}
                {Math.round(d.after * 100)}%
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
