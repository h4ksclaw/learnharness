import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import OpenAI from "openai";

const backendUrl =
  process.env.BACKEND_URL ||
  (process.env.NODE_ENV === "production"
    ? "http://api:8000"
    : "http://localhost:8000");

const openai = new OpenAI({
  baseURL: `${backendUrl}/v1`,
  apiKey: process.env.LLM_API_KEY || "unused",
});

const serviceAdapter = new OpenAIAdapter({ openai });

const runtime = new CopilotRuntime();

const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  serviceAdapter,
  endpoint: "/api/copilotkit",
});

export const POST = handleRequest;
