"use client";

import { useEffect, useState } from "react";
import { apiClient, type OutboundMessage } from "@/lib/api";
import { Settings, Bell, Trash2, ExternalLink } from "lucide-react";

export default function SettingsPage() {
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadNotifications();
    const interval = setInterval(loadNotifications, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-white/[0.05] px-6 py-4">
        <Settings className="h-5 w-5 text-[#10b981]" />
        <h1 className="text-lg font-semibold text-[#f7f8f8]">Settings</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl space-y-8">
          {/* Notifications */}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-[#8a8f98]" />
                <h2 className="text-sm font-semibold text-[#f7f8f8]">
                  Agent Notifications
                </h2>
              </div>
              <button
                onClick={loadNotifications}
                className="text-xs text-[#10b981] hover:text-[#34d399]"
              >
                Refresh
              </button>
            </div>
            <div className="space-y-2">
              {loadingNotifs ? (
                <div className="rounded-lg border border-white/[0.08] bg-[#191a1b] p-4 text-sm text-[#8a8f98]">
                  Loading...
                </div>
              ) : notifications.length === 0 ? (
                <div className="rounded-lg border border-white/[0.08] bg-[#191a1b] p-4 text-center text-sm text-[#62666d]">
                  No pending notifications from agents.
                </div>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    className="flex items-start justify-between rounded-lg border border-white/[0.08] bg-[#191a1b] p-4"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-[#10b981]/10 px-1.5 py-0.5 text-xs text-[#10b981]">
                          {n.channel}
                        </span>
                        <span className="text-xs text-[#62666d]">
                          {new Date(n.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-[#f7f8f8]">{n.message}</p>
                    </div>
                    <button
                      onClick={async () => {
                        await apiClient.markOutboundSent(n.id);
                        loadNotifications();
                      }}
                      className="rounded-lg p-1.5 text-[#8a8f98] hover:bg-white/[0.06] hover:text-[#f7f8f8]"
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
            <h2 className="mb-3 text-sm font-semibold text-[#d0d6e0]">
              About
            </h2>
            <div className="rounded-lg border border-white/[0.08] bg-[#191a1b] p-4 text-sm text-[#d0d6e0]">
              <p>
                LearnHarness — an open-source adaptive learning platform.
                Create AI tutors that track progress and adapt to each learner.
              </p>
              <p className="mt-3">
                <a
                  href="https://github.com/h4ksclaw/learnharness"
                  className="inline-flex items-center gap-1.5 text-[#10b981] hover:underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
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
