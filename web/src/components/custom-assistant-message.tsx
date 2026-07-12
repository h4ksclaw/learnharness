"use client";

import { useState } from "react";
import { AssistantMessage } from "@copilotkit/react-ui";
import type { AssistantMessageProps } from "@copilotkit/react-ui";
import { GitBranch, MessageSquarePlus } from "lucide-react";

/**
 * Custom assistant message wrapper that adds a "Branch" button
 * to open subthreads on bot replies only.
 */
function CustomAssistantMessage(props: AssistantMessageProps) {
  const [hovered, setHovered] = useState(false);
  const [showSubthread, setShowSubthread] = useState(false);

  const isGenerating = props.isGenerating;
  const hasContent = props.message?.content && props.message.content.length > 0;
  const canBranch = hasContent && !isGenerating;

  return (
    <div
      className="group relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Default CopilotKit assistant message */}
      <AssistantMessage {...props} />

      {/* Branch button — only on bot replies, only when not generating */}
      {canBranch && (
        <div
          className={`absolute -right-1 -top-1 flex gap-1 transition-opacity ${
            hovered || showSubthread ? "opacity-100" : "opacity-0"
          }`}
        >
          <button
            onClick={() => setShowSubthread(!showSubthread)}
            className="flex items-center gap-1 rounded-md border border-white/[0.08] bg-[#191a1b] px-2 py-1 text-[10px] font-medium text-[#8a8f98] hover:bg-white/[0.08] hover:text-[#f7f8f8]"
            title="Open subthread"
          >
            <GitBranch className="h-3 w-3" />
            Branch
          </button>
        </div>
      )}

      {/* Subthread panel — inline expandable */}
      {showSubthread && canBranch && (
        <div className="mt-2 rounded-lg border border-white/[0.05] bg-[#0f1011] p-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs text-[#8a8f98]">
            <MessageSquarePlus className="h-3 w-3" />
            <span>Subthread</span>
          </div>
          <div className="flex gap-2">
            <input
              placeholder="Reply in subthread..."
              autoFocus
              className="flex-1 rounded-md border border-white/[0.08] bg-[#191a1b] px-2.5 py-1.5 text-xs text-[#f7f8f8] placeholder-[#62666d] focus:border-[#10b981] focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && e.currentTarget.value.trim()) {
                  // For now, subthreads are client-side only
                  // In future this would create a real subthread via API
                  e.currentTarget.value = "";
                }
              }}
            />
            <button className="rounded-md bg-[#10b981] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#34d399]">
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default CustomAssistantMessage;
