"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { apiClient, type Agent } from "@/lib/api";
import { CopilotChat } from "@copilotkit/react-ui";
import type { AssistantMessageProps } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import {
  Hash,
  Plus,
} from "lucide-react";
import CustomAssistantMessage from "@/components/custom-assistant-message";

interface Thread {
  id: string;
  title: string;
}

// Lazy initial state from localStorage — no effect needed
function loadSession() {
  if (typeof window === "undefined") return null;
  try {
    const saved = localStorage.getItem("lh_session");
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

export default function ChatPage() {
  // Restore session synchronously via lazy initial state
  const [session] = useState(loadSession);

  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>(
    session?.selectedAgent ?? "",
  );
  const [learnerId, setLearnerId] = useState<string>(
    session?.learnerId ?? "",
  );
  const [threads, setThreads] = useState<Thread[]>(session?.threads ?? []);
  const [activeThread, setActiveThread] = useState<string>(
    session?.activeThread ?? "",
  );
  const [showNewThread, setShowNewThread] = useState(false);
  const [newThreadTitle, setNewThreadTitle] = useState("");
  const threadCounter = useRef(0);

  // Restore thread counter to prevent ID collisions
  useEffect(() => {
    if (session?.threads?.length > 0) {
      const maxNum = session.threads.reduce((max: number, t: Thread) => {
        const m = t.id?.match(/thread_(\d+)/);
        return m ? Math.max(max, parseInt(m[1], 10)) : max;
      }, 0);
      threadCounter.current = maxNum;
    }
    // If no threads after hydration, create the first one
    if (threads.length === 0) {
      const id = `thread_${++threadCounter.current}`;
      setThreads([{ id, title: "General" }]);
      setActiveThread(id);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load agents
  useEffect(() => {
    apiClient
      .listAgents()
      .then((data) => {
        setAgents(data);
        if (data.length > 0 && !selectedAgent) {
          setSelectedAgent(data[0].id);
        }
      })
      .catch(() => setAgents([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist session whenever it changes
  useEffect(() => {
    localStorage.setItem(
      "lh_session",
      JSON.stringify({ learnerId, threads, activeThread, selectedAgent }),
    );
  }, [learnerId, threads, activeThread, selectedAgent]);

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

  const createThread = (title: string) => {
    const id = `thread_${++threadCounter.current}`;
    const thread: Thread = { id, title };
    setThreads((prev) => [...prev, thread]);
    setActiveThread(id);
    setShowNewThread(false);
    setNewThreadTitle("");
    return id;
  };

  const openNewThreadModal = () => {
    setNewThreadTitle("");
    setShowNewThread(true);
  };

  const currentThread = threads.find((t) => t.id === activeThread);

  return (
    <div className="flex h-full">
      {/* Threads sidebar */}
      <div className="flex w-60 flex-col border-r border-white/[0.05] bg-[#0f1011]">
        <div className="flex h-14 items-center justify-between px-4">
          <span className="text-sm font-semibold text-[#f7f8f8]">Threads</span>
          <button
            onClick={openNewThreadModal}
            className="rounded p-1 text-[#8a8f98] hover:bg-white/[0.06] hover:text-[#f7f8f8]"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Agent selector */}
        <div className="px-3 pb-2">
          <select
            value={selectedAgent}
            onChange={(e) => {
              setSelectedAgent(e.target.value);
              if (e.target.value && !learnerId) {
                ensureLearner();
              }
            }}
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
          {threads.length === 0 ? (
            <p className="px-2 py-4 text-xs text-[#62666d]">
              No threads yet. Click + to start.
            </p>
          ) : (
            threads.map((t) => (
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
              </div>
            ))
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
                <span className="font-semibold text-[#f7f8f8]">
                  {currentThread.title}
                </span>
              </div>
            </div>

            {/* CopilotChat */}
            <div
              className="flex-1 overflow-hidden"
              style={
                {
                  "--copilot-kit-background-color": "#08090a",
                  "--copilot-kit-primary-color": "#10b981",
                  "--copilot-kit-secondary-color": "#0f1011",
                  "--copilot-kit-tertiary-color": "#191a1b",
                  "--copilot-kit-text-color": "#f7f8f8",
                  "--copilot-kit-border-color": "rgba(255,255,255,0.08)",
                  "--copilot-kit-border-radius": "0.75rem",
                  "--copilot-kit-font-family":
                    "var(--font-inter), system-ui, sans-serif",
                } as React.CSSProperties
              }
            >
              <CopilotChat
                className="h-full"
                AssistantMessage={
                  CustomAssistantMessage as React.ComponentType<AssistantMessageProps>
                }
                instructions={
                  selectedAgent
                    ? `You are a learning agent (agent_id: ${selectedAgent}). Help the learner practice and learn.`
                    : undefined
                }
                labels={{
                  title: currentThread.title,
                  placeholder: selectedAgent
                    ? "Type a message..."
                    : "Select an agent first",
                }}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center text-center">
            <p className="text-sm text-[#62666d]">
              Create a thread to start chatting
            </p>
            <button
              onClick={openNewThreadModal}
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
              New Thread
            </h2>
            <input
              value={newThreadTitle}
              onChange={(e) => setNewThreadTitle(e.target.value)}
              placeholder="e.g. German grammar practice"
              onKeyDown={(e) => {
                if (e.key === "Enter" && newThreadTitle.trim()) {
                  createThread(newThreadTitle);
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
                  newThreadTitle.trim() && createThread(newThreadTitle)
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
