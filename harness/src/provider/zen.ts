import OpenAI from "openai";
import type { Provider, ProviderOptions, StreamEvent, Message, MessageContent, ToolSchema } from "./provider.ts";

const client = new OpenAI({
  baseURL: "https://opencode.ai/zen/v1",
  apiKey: process.env.ZEN_API_KEY ?? process.env.OPENAI_API_KEY ?? "",
});

export const zenProvider: Provider = {
  async *stream(opts: ProviderOptions): AsyncGenerator<StreamEvent> {
    const openaiMessages = toOpenAIMessages(opts.messages);
    const tools = opts.tools.length > 0 ? toOpenAITools(opts.tools) : undefined;

    const stream = await client.chat.completions.create({
      model: opts.model,
      messages: [
        ...(opts.system ? [{ role: "system" as const, content: opts.system }] : []),
        ...openaiMessages,
      ],
      tools,
      tool_choice: tools ? "auto" : undefined,
      max_tokens: opts.maxTokens ?? 8096,
      stream: true,
    });

    if (opts.signal) {
      opts.signal.addEventListener("abort", () => stream.controller.abort());
    }

    // Collect tool call argument chunks (OpenAI streams them incrementally)
    const toolCallBuffers = new Map<number, { id: string; name: string; args: string }>();
    let finishReason = "end_turn";

    for await (const chunk of stream) {
      const choice = chunk.choices[0];
      if (!choice) continue;

      const delta = choice.delta;

      // Text token
      if (delta.content) {
        yield { type: "text-delta", text: delta.content };
      }

      // Tool call streaming — accumulate argument JSON
      if (delta.tool_calls) {
        for (const tc of delta.tool_calls) {
          const idx = tc.index ?? 0;
          if (!toolCallBuffers.has(idx)) {
            toolCallBuffers.set(idx, { id: tc.id ?? "", name: tc.function?.name ?? "", args: "" });
          }
          const buf = toolCallBuffers.get(idx)!;
          if (tc.id) buf.id = tc.id;
          if (tc.function?.name) buf.name = tc.function.name;
          if (tc.function?.arguments) buf.args += tc.function.arguments;
        }
      }

      if (choice.finish_reason) {
        finishReason = choice.finish_reason;
      }
    }

    // Emit complete tool calls after stream ends
    for (const [, tc] of toolCallBuffers) {
      let input: unknown = {};
      try { input = JSON.parse(tc.args); } catch { /* malformed JSON → empty */ }
      yield { type: "tool-call", toolCallId: tc.id, toolName: tc.name, toolInput: input };
    }

    yield { type: "finish", stopReason: finishReason };
  },
};

// ─── Format converters ────────────────────────────────────────────────────────

function toOpenAIMessages(messages: Message[]): OpenAI.ChatCompletionMessageParam[] {
  const result: OpenAI.ChatCompletionMessageParam[] = [];

  for (const msg of messages) {
    // Simple string content
    if (typeof msg.content === "string") {
      result.push({ role: msg.role as "user" | "assistant", content: msg.content });
      continue;
    }

    const parts = msg.content as MessageContent[];

    if (msg.role === "assistant") {
      // Check for tool_use blocks
      const toolUseBlocks = parts.filter((p) => p.type === "tool_use");
      const textBlocks = parts.filter((p) => p.type === "text");
      const textContent = textBlocks.map((p) => p.text ?? "").join("") || undefined;

      if (toolUseBlocks.length > 0) {
        result.push({
          role: "assistant",
          content: textContent ?? null,
          tool_calls: toolUseBlocks.map((p) => ({
            id: p.id!,
            type: "function" as const,
            function: { name: p.name!, arguments: JSON.stringify(p.input ?? {}) },
          })),
        });
      } else {
        result.push({ role: "assistant", content: textContent ?? "" });
      }
    } else if (msg.role === "user") {
      // Check for tool_result blocks
      const toolResultBlocks = parts.filter((p) => p.type === "tool_result");
      const textBlocks = parts.filter((p) => p.type === "text");

      if (toolResultBlocks.length > 0) {
        // OpenAI: each tool result is a separate "tool" role message
        for (const tr of toolResultBlocks) {
          const content =
            typeof tr.content === "string"
              ? tr.content
              : Array.isArray(tr.content)
              ? tr.content.map((c) => (typeof c === "string" ? c : c.text ?? "")).join("")
              : "";
          result.push({ role: "tool", tool_call_id: tr.tool_use_id!, content });
        }
        if (textBlocks.length > 0) {
          result.push({ role: "user", content: textBlocks.map((p) => p.text ?? "").join("") });
        }
      } else {
        // Regular user message with possible image content
        const hasImages = parts.some((p) => p.type === "image");
        if (hasImages) {
          result.push({
            role: "user",
            content: parts.map((p) => {
              if (p.type === "text") return { type: "text" as const, text: p.text ?? "" };
              if (p.type === "image" && p.source?.type === "base64") {
                return {
                  type: "image_url" as const,
                  image_url: { url: `data:${p.source.media_type};base64,${p.source.data}` },
                };
              }
              return { type: "text" as const, text: "" };
            }),
          });
        } else {
          result.push({ role: "user", content: parts.map((p) => p.text ?? "").join("") });
        }
      }
    }
  }

  return result;
}

function toOpenAITools(tools: ToolSchema[]): OpenAI.ChatCompletionTool[] {
  return tools.map((t) => ({
    type: "function" as const,
    function: {
      name: t.name,
      description: t.description,
      parameters: t.input_schema as Record<string, unknown>,
    },
  }));
}
