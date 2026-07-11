/**
 * LearnHarness API client wrapper.
 * Uses fetch — no external deps needed.
 * The OpenAPI spec at /openapi.json documents all endpoints.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api" : "http://api:8000");

export interface Agent {
  id: string;
  name: string;
  master_prompt: string;
  tools: string[];
  channels: Record<string, unknown>;
  heartbeat_interval: number;
  llm_model: string | null;
  active: boolean;
  created_at: string;
}

export interface Learner {
  id: string;
  agent_id: string;
  name: string;
  overall_mastery: number;
  created_at: string;
  last_active: string | null;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
}

export interface Correction {
  original: string;
  corrected: string;
  rule: string;
  concept_id: string | null;
  severity: "error" | "warning" | "suggestion";
}

export interface MasteryDelta {
  concept_id: string;
  concept_name: string;
  before: number;
  after: number;
  direction: "up" | "down" | "same";
}

export interface ChatResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }[];
  corrections: Correction[];
  mastery_deltas: MasteryDelta[];
  concepts_detected: string[];
  reviews_due: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
}

export interface MasteryOut {
  concept_id: string;
  concept_name: string;
  category: string;
  p_mastery: number;
  interactions_count: number;
  correct_count: number;
  last_updated: string;
}

export interface CategoryProgress {
  category: string;
  concept_count: number;
  avg_mastery: number;
  concepts: Record<string, unknown>[];
}

export interface OutboundMessage {
  id: number;
  agent_id: string;
  learner_id: string | null;
  channel: string;
  message: string;
  sent: boolean;
  created_at: string;
}

async function api<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const apiClient = {
  // Agents
  listAgents: () => api<Agent[]>("/v1/agents"),
  getAgent: (id: string) => api<Agent>(`/v1/agents/${id}`),
  createAgent: (data: Partial<Agent>) =>
    api<Agent>("/v1/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: Partial<Agent>) =>
    api<Agent>(`/v1/agents/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteAgent: (id: string) =>
    api<void>(`/v1/agents/${id}`, { method: "DELETE" }),

  // Learners
  createLearner: (agentId: string, name: string) =>
    api<Learner>("/v1/learners", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, name }),
    }),
  getLearner: (id: string) => api<Learner>(`/v1/learners/${id}`),

  // Chat
  chat: (
    agentId: string,
    learnerId: string,
    messages: ChatMessage[],
    sessionId?: string,
  ) =>
    api<ChatResponse>("/v1/chat/completions", {
      method: "POST",
      body: JSON.stringify({
        agent_id: agentId,
        learner_id: learnerId,
        session_id: sessionId,
        messages,
      }),
    }),

  // Mastery
  getMastery: (learnerId: string) =>
    api<MasteryOut[]>(`/v1/mastery/${learnerId}`),
  getCategoryProgress: (learnerId: string) =>
    api<CategoryProgress[]>(`/v1/mastery/${learnerId}/categories`),

  // Outbound messages
  getOutbound: (agentId?: string) =>
    api<OutboundMessage[]>(
      `/v1/outbound${agentId ? `?agent_id=${agentId}` : ""}`,
    ),
  markOutboundSent: (id: number) =>
    api<void>(`/v1/outbound/${id}/sent`, { method: "POST" }),
};
