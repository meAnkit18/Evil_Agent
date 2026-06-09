import type { Message, MessageContent } from "../provider/provider.ts";

export type { Message, MessageContent };

export interface StoredMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string; // JSON
  created_at: number;
}

export function buildToolResultMessages(
  toolCalls: Array<{ id: string; name: string; input: unknown }>,
  toolResults: Array<{ id: string; output: string; metadata?: Record<string, unknown> }>
): Message[] {
  // Assistant message with tool_use blocks
  const assistantContent: MessageContent[] = toolCalls.map((tc) => ({
    type: "tool_use",
    id: tc.id,
    name: tc.name,
    input: tc.input,
  }));

  // User message with tool_result blocks
  const userContent: MessageContent[] = toolResults.map((tr) => {
    const metadata = tr.metadata;

    // If the result is a screenshot (image), pass it as image content
    if (metadata?.imageBase64) {
      return {
        type: "tool_result",
        tool_use_id: tr.id,
        content: [
          {
            type: "image",
            source: {
              type: "base64",
              media_type: (metadata.mediaType as string) ?? "image/png",
              data: metadata.imageBase64 as string,
            },
          },
        ],
      };
    }

    return {
      type: "tool_result",
      tool_use_id: tr.id,
      content: tr.output.slice(0, 100_000),
    };
  });

  return [
    { role: "assistant", content: assistantContent },
    { role: "user", content: userContent },
  ];
}
