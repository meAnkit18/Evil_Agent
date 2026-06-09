import Anthropic from "@anthropic-ai/sdk";
import type { Provider, ProviderOptions, StreamEvent } from "./provider.ts";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

export const anthropicProvider: Provider = {
  async *stream(opts: ProviderOptions): AsyncGenerator<StreamEvent> {
    const stream = client.messages.stream({
      model: opts.model,
      max_tokens: opts.maxTokens ?? 8096,
      system: opts.system,
      messages: opts.messages as Anthropic.MessageParam[],
      tools: opts.tools as Anthropic.Tool[],
    });

    if (opts.signal) {
      opts.signal.addEventListener("abort", () => stream.abort());
    }

    for await (const event of stream) {
      if (event.type === "content_block_delta") {
        if (event.delta.type === "text_delta") {
          yield { type: "text-delta", text: event.delta.text };
        }
        if (event.delta.type === "input_json_delta") {
          // Tool input streaming — we collect it via message_stop
        }
      }

      if (event.type === "message_stop") {
        const message = await stream.finalMessage();
        for (const block of message.content) {
          if (block.type === "tool_use") {
            yield {
              type: "tool-call",
              toolCallId: block.id,
              toolName: block.name,
              toolInput: block.input,
            };
          }
        }
        yield {
          type: "finish",
          stopReason: message.stop_reason ?? "end_turn",
        };
      }
    }
  },
};
