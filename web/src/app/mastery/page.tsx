"use client";

import { useEffect, useState } from "react";
import {
  apiClient,
  type CategoryProgress,
  type MasteryOut,
} from "@/lib/api";
import { Brain, TrendingUp, Target, BookOpen } from "lucide-react";

export default function MasteryPage() {
  const [learnerId, setLearnerId] = useState("");
  const [mastery, setMastery] = useState<MasteryOut[]>([]);
  const [categories, setCategories] = useState<CategoryProgress[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Read learner ID from the shared session
    try {
      const session = JSON.parse(localStorage.getItem("lh_session") || "{}");
      if (session.learnerId) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLearnerId(session.learnerId);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (learnerId) {
      // Sync to shared session so chat page can use it too
      try {
        const session = JSON.parse(localStorage.getItem("lh_session") || "{}");
        session.learnerId = learnerId;
        localStorage.setItem("lh_session", JSON.stringify(session));
      } catch {
        // ignore
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLoading(true);
      Promise.all([
        apiClient.getMastery(learnerId).catch(() => []),
        apiClient.getCategoryProgress(learnerId).catch(() => []),
      ]).then(([m, c]) => {
        setMastery(m);
        setCategories(c);
        setLoading(false);
      });
    }
  }, [learnerId]);

  const overallMastery =
    mastery.length > 0
      ? mastery.reduce((s, m) => s + m.p_mastery, 0) / mastery.length
      : 0;

  const mastered = mastery.filter((m) => m.p_mastery >= 0.7).length;
  const learning = mastery.filter(
    (m) => m.p_mastery >= 0.3 && m.p_mastery < 0.7,
  ).length;
  const weak = mastery.filter((m) => m.p_mastery < 0.3).length;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-white/[0.05] px-6 py-4">
        <Brain className="h-5 w-5 text-[#10b981]" />
        <h1 className="text-lg font-semibold text-[#f7f8f8]">Knowledge State</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        {!learnerId ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Brain className="mb-4 h-12 w-12 text-[#62666d]" />
            <p className="text-sm text-[#8a8f98]">
              Start a chat first to build your knowledge profile.
            </p>
            <p className="mt-1 text-xs text-[#62666d]">
              Your progress will appear here automatically.
            </p>
          </div>
        ) : loading ? (
          <div className="text-sm text-[#8a8f98]">Loading...</div>
        ) : (
          <div className="space-y-6">
            {/* Stats cards */}
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                label="Overall"
                value={`${Math.round(overallMastery * 100)}%`}
                icon={TrendingUp}
                color="emerald"
              />
              <StatCard
                label="Mastered"
                value={String(mastered)}
                icon={Target}
                color="blue"
              />
              <StatCard
                label="Learning"
                value={String(learning)}
                icon={BookOpen}
                color="amber"
              />
              <StatCard
                label="Needs Work"
                value={String(weak)}
                icon={Brain}
                color="red"
              />
            </div>

            {/* Category breakdown */}
            {categories.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold text-[#d0d6e0]">
                  By Category
                </h2>
                <div className="space-y-3">
                  {categories.map((cat) => (
                    <div
                      key={cat.category}
                      className="rounded-lg border border-white/[0.08] bg-[#191a1b] p-4"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-[#f7f8f8]">{cat.category}</span>
                          <span className="text-xs text-[#62666d]">
                            ({cat.concept_count} concepts)
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-32 overflow-hidden rounded-full bg-white/[0.06]">
                            <div
                              className={`h-full rounded-full ${
                                cat.avg_mastery >= 0.7
                                  ? "bg-emerald-500"
                                  : cat.avg_mastery >= 0.3
                                    ? "bg-amber-500"
                                    : "bg-red-500"
                              }`}
                              style={{
                                width: `${Math.round(cat.avg_mastery * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs font-medium text-[#d0d6e0]">
                            {Math.round(cat.avg_mastery * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Detailed concepts */}
            {mastery.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold text-[#d0d6e0]">
                  All Concepts ({mastery.length})
                </h2>
                <div className="grid gap-2">
                  {mastery
                    .sort((a, b) => a.p_mastery - b.p_mastery)
                    .map((m) => (
                      <div
                        key={m.concept_id}
                        className="flex items-center justify-between rounded-lg border border-white/[0.08] bg-[#191a1b] px-4 py-2"
                      >
                        <div>
                          <span className="text-sm font-medium text-[#f7f8f8]">
                            {m.concept_name}
                          </span>
                          <span className="ml-2 text-xs text-[#62666d]">
                            {m.category}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-[#62666d]">
                            {m.correct_count}/{m.interactions_count} correct
                          </span>
                          <div className="h-2 w-20 overflow-hidden rounded-full bg-white/[0.06]">
                            <div
                              className={`h-full rounded-full ${
                                m.p_mastery >= 0.7
                                  ? "bg-emerald-500"
                                  : m.p_mastery >= 0.3
                                    ? "bg-amber-500"
                                    : "bg-red-500"
                              }`}
                              style={{
                                width: `${Math.round(m.p_mastery * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="w-10 text-right text-xs font-medium">
                            {Math.round(m.p_mastery * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: "emerald" | "blue" | "amber" | "red";
}) {
  const colors = {
    emerald: "text-[#10b981] bg-[#10b981]/10",
    blue: "text-blue-400 bg-blue-500/10",
    amber: "text-amber-400 bg-amber-500/10",
    red: "text-red-400 bg-red-500/10",
  };
  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#191a1b] p-4">
      <div
        className={`mb-2 flex h-8 w-8 items-center justify-center rounded-lg ${colors[color]}`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="text-2xl font-bold text-[#f7f8f8]">{value}</div>
      <div className="text-xs text-[#8a8f98]">{label}</div>
    </div>
  );
}
