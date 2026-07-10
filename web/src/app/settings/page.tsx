"use client";

import { useEffect, useState } from "react";
import { apiClient, type OutboundMessage } from "@/lib/api";
import { Settings, Bell, Server, Trash2 } from "lucide-react";

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  );
  const [notifications, setNotifications] = useState<OutboundMessage[]>([]);
  const [loadingNotifs, setLoadingNotifs] = useState(false);

  const loadNotifications = async () => {
    setLoadingNotifs(true);
    try {
      const data = await apiClient.getOutbound();
      setNotifications(data);
    } catch {
      setNotifications([]);
    }
    setLoadingNotifs(false);
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-zinc-800 px-6 py-4">
        <Settings className="h-5 w-5 text-emerald-400" />
        <h1 className="text-lg font-semibold">Settings</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl space-y-8">
          {/* API Connection */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <Server className="h-4 w-4 text-zinc-500" />
              <h2 className="text-sm font-semibold">API Connection</h2>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <label className="mb-1 block text-xs text-zinc-500">
                Backend URL
              </label>
              <input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
              />
              <p className="mt-2 text-xs text-zinc-600">
                Set NEXT_PUBLIC_API_URL at build time to change the default.
              </p>
            </div>
          </section>

          {/* Notifications */}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-zinc-500" />
                <h2 className="text-sm font-semibold">
                  Agent Notifications
                </h2>
              </div>
              <button
                onClick={loadNotifications}
                className="text-xs text-emerald-400 hover:text-emerald-300"
              >
                Refresh
              </button>
            </div>
            <div className="space-y-2">
              {loadingNotifs ? (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-500">
                  Loading...
                </div>
              ) : notifications.length === 0 ? (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-center text-sm text-zinc-600">
                  No pending notifications from agents.
                </div>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    className="flex items-start justify-between rounded-xl border border-zinc-800 bg-zinc-900 p-4"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-xs text-emerald-400">
                          {n.channel}
                        </span>
                        <span className="text-xs text-zinc-600">
                          {new Date(n.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="mt-1 text-sm">{n.message}</p>
                    </div>
                    <button
                      onClick={async () => {
                        await apiClient.markOutboundSent(n.id);
                        loadNotifications();
                      }}
                      className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-white"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* About */}
          <section>
            <h2 className="mb-3 text-sm font-semibold text-zinc-400">
              About
            </h2>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-400">
              <p>
                LearnHarness — open-source adaptive learning platform with FSRS
                spaced repetition, BKT knowledge tracing, and LLM-powered
                knowledge graphs.
              </p>
              <p className="mt-2 text-xs text-zinc-600">
                <a
                  href="https://github.com/h4ksclaw/learnharness"
                  className="text-emerald-400 hover:underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  github.com/h4ksclaw/learnharness
                </a>
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
