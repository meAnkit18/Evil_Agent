export interface Message {
  role: "user" | "assistant" | "tool";
  content: string | MessageContent[];
}

export interface MessageContent {
  type: "text" | "image" | "tool_use" | "tool_result";
  text?: string;
  source?: { type: "base64"; media_type: string; data: string };
  id?: string;
  name?: string;
  input?: unknown;
  tool_use_id?: string;
  content?: string | MessageContent[];
}

export interface ToolSchema {
  name: string;
  description: string;
  input_schema: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface StreamEvent {
  type: "text-delta" | "tool-call" | "finish" | "error";
  text?: string;
  toolCallId?: string;
  toolName?: string;
  toolInput?: unknown;
  error?: string;
  stopReason?: string;
}

export interface ProviderOptions {
  model: string;
  messages: Message[];
  tools: ToolSchema[];
  system?: string;
  maxTokens?: number;
  signal?: AbortSignal;
}

export interface Provider {
  stream(opts: ProviderOptions): AsyncGenerator<StreamEvent>;
}
