"use client";

import { useEffect, useState, useCallback } from "react";
import { apiClient, type Agent } from "@/lib/api";
import { Plus, Trash2, Pencil, Bot, X, Hash, MessageCircle, Send } from "lucide-react";

const AVAILABLE_TOOLS = ["web_search", "browse_url", "wikipedia", "arxiv"];

// ─── Channel config types ───

interface IRCConfig {
  host: string;
  port: number;
  nick: string;
  channels: string;
  password: string;
  ssl: boolean;
  allowed_users: string;
  require_mention: boolean;
}

interface DiscordConfig {
  token: string;
  allowed_users: string;
  allowed_channels: string;
  require_mention: boolean;
}

interface TelegramConfig {
  token: string;
  allowed_users: string;
  require_mention: boolean;
  welcome_message: string;
}

const emptyIRC: IRCConfig = { host: "", port: 6667, nick: "", channels: "", password: "", ssl: false, allowed_users: "", require_mention: true };
const emptyDiscord: DiscordConfig = { token: "", allowed_users: "", allowed_channels: "", require_mention: true };
const emptyTelegram: TelegramConfig = { token: "", allowed_users: "", require_mention: false, welcome_message: "" };

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      const data = await apiClient.listAgents();
      setAgents(data);
    } catch {
      setAgents([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
  const [ircEnabled, setIrcEnabled] = useState(!!agent?.channels?.irc);
  const [discordEnabled, setDiscordEnabled] = useState(!!agent?.channels?.discord);
  const [telegramEnabled, setTelegramEnabled] = useState(!!agent?.channels?.telegram);
  const [irc, setIrc] = useState<IRCConfig>({
    ...emptyIRC,
    ...(agent?.channels?.irc as Partial<IRCConfig> || {}),
    channels: Array.isArray(agent?.channels?.irc?.channels) ? agent!.channels.irc.channels.join(", ") : "",
    allowed_users: Array.isArray(agent?.channels?.irc?.allowed_users) ? agent!.channels.irc.allowed_users.join(", ") : "",
    port: agent?.channels?.irc?.port ?? 6667,
    ssl: agent?.channels?.irc?.ssl ?? false,
    require_mention: agent?.channels?.irc?.require_mention ?? true,
  });
  const [discord, setDiscord] = useState<DiscordConfig>({
    ...emptyDiscord,
    ...(agent?.channels?.discord as Partial<DiscordConfig> || {}),
    allowed_users: Array.isArray(agent?.channels?.discord?.allowed_users) ? agent!.channels.discord.allowed_users.join(", ") : "",
    allowed_channels: Array.isArray(agent?.channels?.discord?.allowed_channels) ? agent!.channels.discord.allowed_channels.join(", ") : "",
    require_mention: agent?.channels?.discord?.require_mention ?? true,
  });
  const [telegram, setTelegram] = useState<TelegramConfig>({
    ...emptyTelegram,
    ...(agent?.channels?.telegram as Partial<TelegramConfig> || {}),
    allowed_users: Array.isArray(agent?.channels?.telegram?.allowed_users) ? agent!.channels.telegram.allowed_users.join(", ") : "",
    require_mention: agent?.channels?.telegram?.require_mention ?? false,
  });
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
      const channels = {} as Record<string, Record<string, unknown>>;
      if (ircEnabled && irc.host) {
        channels.irc = {
          host: irc.host,
          port: irc.port,
          nick: irc.nick,
          channels: irc.channels.split(",").map((s) => s.trim()).filter(Boolean),
          password: irc.password || null,
          ssl: irc.ssl,
          allowed_users: irc.allowed_users.split(",").map((s) => s.trim()).filter(Boolean),
          require_mention: irc.require_mention,
        };
      }
      if (discordEnabled && discord.token) {
        channels.discord = {
          token: discord.token,
          allowed_users: discord.allowed_users.split(",").map((s) => s.trim()).filter(Boolean),
          allowed_channels: discord.allowed_channels.split(",").map((s) => Number(s.trim())).filter((n) => !isNaN(n)),
          require_mention: discord.require_mention,
        };
      }
      if (telegramEnabled && telegram.token) {
        channels.telegram = {
          token: telegram.token,
          allowed_users: telegram.allowed_users.split(",").map((s) => s.trim()).filter(Boolean),
          require_mention: telegram.require_mention,
          welcome_message: telegram.welcome_message || null,
        };
      }
      const data = {
        name,
        master_prompt: masterPrompt,
        tools,
        channels,
        heartbeat_interval: heartbeat,
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
          </div>

          <div>
            <label className="mb-2 block text-sm text-zinc-400">Channels</label>
            <div className="space-y-3">
              {/* IRC */}
              <div className={`rounded-lg border ${ircEnabled ? "border-emerald-800 bg-emerald-950/20" : "border-zinc-800 bg-zinc-950"} p-3`}>
                <button
                  type="button"
                  onClick={() => setIrcEnabled(!ircEnabled)}
                  className="flex w-full items-center gap-2 text-left"
                >
                  <Hash className="h-4 w-4 text-zinc-500" />
                  <span className="text-sm font-medium">IRC</span>
                  <span className={`ml-auto h-3 w-3 rounded-full ${ircEnabled ? "bg-emerald-500" : "bg-zinc-700"}`} />
                </button>
                {ircEnabled && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <input value={irc.host} onChange={(e) => setIrc({ ...irc, host: e.target.value })} placeholder="irc.libera.chat" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input type="number" value={irc.port} onChange={(e) => setIrc({ ...irc, port: Number(e.target.value) })} placeholder="6667" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={irc.nick} onChange={(e) => setIrc({ ...irc, nick: e.target.value })} placeholder="BotNick" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={irc.channels} onChange={(e) => setIrc({ ...irc, channels: e.target.value })} placeholder="#chan1, #chan2" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={irc.password} onChange={(e) => setIrc({ ...irc, password: e.target.value })} placeholder="password (optional)" type="password" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={irc.allowed_users} onChange={(e) => setIrc({ ...irc, allowed_users: e.target.value })} placeholder="allowed users (comma)" className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <label className="flex items-center gap-2 text-xs text-zinc-400 col-span-2">
                      <input type="checkbox" checked={irc.ssl} onChange={(e) => setIrc({ ...irc, ssl: e.target.checked })} className="rounded" />
                      SSL
                      <input type="checkbox" checked={irc.require_mention} onChange={(e) => setIrc({ ...irc, require_mention: e.target.checked })} className="rounded ml-4" />
                      Require mention
                    </label>
                  </div>
                )}
              </div>

              {/* Discord */}
              <div className={`rounded-lg border ${discordEnabled ? "border-indigo-800 bg-indigo-950/20" : "border-zinc-800 bg-zinc-950"} p-3`}>
                <button
                  type="button"
                  onClick={() => setDiscordEnabled(!discordEnabled)}
                  className="flex w-full items-center gap-2 text-left"
                >
                  <MessageCircle className="h-4 w-4 text-zinc-500" />
                  <span className="text-sm font-medium">Discord</span>
                  <span className={`ml-auto h-3 w-3 rounded-full ${discordEnabled ? "bg-indigo-500" : "bg-zinc-700"}`} />
                </button>
                {discordEnabled && (
                  <div className="mt-3 space-y-2">
                    <input value={discord.token} onChange={(e) => setDiscord({ ...discord, token: e.target.value })} placeholder="Bot token" type="password" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={discord.allowed_users} onChange={(e) => setDiscord({ ...discord, allowed_users: e.target.value })} placeholder="allowed user IDs (comma)" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={discord.allowed_channels} onChange={(e) => setDiscord({ ...discord, allowed_channels: e.target.value })} placeholder="allowed channel IDs (comma, empty=all)" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <label className="flex items-center gap-2 text-xs text-zinc-400">
                      <input type="checkbox" checked={discord.require_mention} onChange={(e) => setDiscord({ ...discord, require_mention: e.target.checked })} className="rounded" />
                      Require mention
                    </label>
                  </div>
                )}
              </div>

              {/* Telegram */}
              <div className={`rounded-lg border ${telegramEnabled ? "border-sky-800 bg-sky-950/20" : "border-zinc-800 bg-zinc-950"} p-3`}>
                <button
                  type="button"
                  onClick={() => setTelegramEnabled(!telegramEnabled)}
                  className="flex w-full items-center gap-2 text-left"
                >
                  <Send className="h-4 w-4 text-zinc-500" />
                  <span className="text-sm font-medium">Telegram</span>
                  <span className={`ml-auto h-3 w-3 rounded-full ${telegramEnabled ? "bg-sky-500" : "bg-zinc-700"}`} />
                </button>
                {telegramEnabled && (
                  <div className="mt-3 space-y-2">
                    <input value={telegram.token} onChange={(e) => setTelegram({ ...telegram, token: e.target.value })} placeholder="Bot token" type="password" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={telegram.allowed_users} onChange={(e) => setTelegram({ ...telegram, allowed_users: e.target.value })} placeholder="allowed users @handle (comma)" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <input value={telegram.welcome_message} onChange={(e) => setTelegram({ ...telegram, welcome_message: e.target.value })} placeholder="welcome message (optional)" className="w-full rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs" />
                    <label className="flex items-center gap-2 text-xs text-zinc-400">
                      <input type="checkbox" checked={telegram.require_mention} onChange={(e) => setTelegram({ ...telegram, require_mention: e.target.checked })} className="rounded" />
                      Require mention
                    </label>
                  </div>
                )}
              </div>
            </div>
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
