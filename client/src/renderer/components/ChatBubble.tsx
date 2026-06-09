import React from "react";
import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

export function ChatBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`chat-bubble ${isUser ? "chat-bubble--user" : "chat-bubble--assistant"}`}>
      <div className="chat-bubble__label">{isUser ? "you" : "agent"}</div>
      <div className="chat-bubble__text">
        {message.text}
        {message.streaming && <span className="chat-bubble__cursor" />}
      </div>
    </div>
  );
}
