import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { ChatBubble } from "./ChatBubble";

interface Props {
  messages: ChatMessage[];
  status: "idle" | "busy" | "error";
}

export function ChatArea({ messages, status }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="chat-area chat-area--empty">
        <div className="chat-area__empty-hint">
          {status === "busy" ? "Agent is thinking..." : "Type a prompt to begin"}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-area">
      <div className="chat-area__messages">
        {messages.map((m) => (
          <ChatBubble key={m.id} message={m} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
