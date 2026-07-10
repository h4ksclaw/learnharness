"use client";

import { useEffect, useState, useCallback } from "react";
import { apiClient, type Agent } from "@/lib/api";
import { Plus, Trash2, Pencil, Bot, X } from "lucide-react";

const AVAILABLE_TOOLS = ["web_search", "browse_url", "wikipedia", "arxiv"];

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      const data = await apiClient.listAgents();
      setAgents(data);
    } catch (e) {
      setAgents([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <h1 className="text-lg font-semibold">Agents</h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          <Plus className="h-4 w-4" />
          New Agent
        </button>
      </header>

      {/* Agent list */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-sm text-zinc-500">Loading...</div>
        ) : agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Bot className="mb-4 h-12 w-12 text-zinc-700" />
            <p className="text-sm text-zinc-500">
              No agents yet. Create one to get started.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="group flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 p-4 transition-colors hover:border-zinc-700"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-lg font-bold text-emerald-400">
                    {agent.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{agent.name}</span>
                      {agent.active ? (
                        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400">
                          Active
                        </span>
                      ) : (
                        <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500">
                          Inactive
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 max-w-md truncate text-xs text-zinc-500">
                      {agent.master_prompt.substring(0, 80)}...
                    </p>
                    <div className="mt-1 flex gap-1">
                      {agent.tools?.map((t) => (
                        <span
                          key={t}
                          className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    onClick={() => {
                      setEditing(agent);
                      setShowForm(true);
                    }}
                    className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={async () => {
                      await apiClient.deleteAgent(agent.id);
                      loadAgents();
                    }}
                    className="rounded-lg p-2 text-zinc-400 hover:bg-red-900/30 hover:text-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {showForm && (
        <AgentForm
          agent={editing}
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            loadAgents();
          }}
        />
      )}
    </div>
  );
}

function AgentForm({
  agent,
  onClose,
  onSaved,
}: {
  agent: Agent | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(agent?.name ?? "");
  const [masterPrompt, setMasterPrompt] = useState(
    agent?.master_prompt ?? "",
  );
  const [tools, setTools] = useState<string[]>(agent?.tools ?? []);
  const [heartbeat, setHeartbeat] = useState(
    agent?.heartbeat_interval ?? 300,
  );
  const [llmModel, setLlmModel] = useState(agent?.llm_model ?? "");
  const [channels, setChannels] = useState(
    agent ? JSON.stringify(agent.channels, null, 2) : "{}",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const toggleTool = (t: string) => {
    setTools((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      let parsedChannels = {};
      try {
        parsedChannels = JSON.parse(channels);
      } catch {
        // ignore
      }
      const data = {
        name,
        master_prompt: masterPrompt,
        tools,
        channels: parsedChannels,
        heartbeat_interval: heartbeat,
        llm_model: llmModel || null,
      };
      if (agent) {
        await apiClient.updateAgent(agent.id, data);
      } else {
        await apiClient.createAgent(data);
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save agent");
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {agent ? "Edit Agent" : "Create Agent"}
          </h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-zinc-400">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="German Buddy"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-zinc-400">
              Master Prompt
            </label>
            <textarea
              value={masterPrompt}
              onChange={(e) => setMasterPrompt(e.target.value)}
              placeholder="You are a friendly German tutor. Only respond in German. Correct mistakes gently."
              rows={4}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
            />
            <p className="mt-1 text-xs text-zinc-600">
              This defines the agent&apos;s entire behavior — language, tone,
              domain, pedagogy.
            </p>
          </div>

          <div>
            <label className="mb-2 block text-sm text-zinc-400">Tools</label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_TOOLS.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleTool(t)}
                  className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    tools.includes(t)
                      ? "bg-emerald-600 text-white"
                      : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm text-zinc-400">
                Heartbeat (seconds)
              </label>
              <input
                type="number"
                value={heartbeat}
                onChange={(e) => setHeartbeat(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-zinc-400">
                LLM Model (optional override)
              </label>
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder="qwen2.5:3b"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm text-zinc-400">
              Channels (JSON)
            </label>
            <textarea
              value={channels}
              onChange={(e) => setChannels(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs focus:border-emerald-600 focus:outline-none"
            />
            <p className="mt-1 text-xs text-zinc-600">
              Configure delivery channels (irc, telegram, discord, etc.)
            </p>
          </div>

          {error && (
            <div className="rounded-lg bg-red-900/30 p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name || !masterPrompt}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
            >
              {saving ? "Saving..." : agent ? "Save" : "Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
