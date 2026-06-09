import { sessionStore } from "./session.ts";
import { toolRegistry } from "../tool/registry.ts";
import { anthropicProvider } from "../provider/anthropic.ts";
import { zenProvider } from "../provider/zen.ts";
import { getAgent } from "../agent/agents.ts";
import { bus } from "../events/bus.ts";
import { buildToolResultMessages } from "./message.ts";
import type { Message, Provider } from "../provider/provider.ts";

function getProvider(): Provider {
  return process.env.ACTIVE_PROVIDER === "zen" ? zenProvider : anthropicProvider;
}

const activeSessions = new Map<string, AbortController>();

export async function runAgentLoop(
  sessionId: string,
  userPrompt: string,
  workingDir: string
): Promise<void> {
  const session = sessionStore.get(sessionId);
  if (!session) throw new Error(`Session not found: ${sessionId}`);

  // Cancel any running loop for this session
  activeSessions.get(sessionId)?.abort();
  const controller = new AbortController();
  activeSessions.set(sessionId, controller);

  const emit = bus.emit.bind(bus);

  bus.emit({ type: "session.status", sessionID: sessionId, status: "busy" });

  try {
    // Persist user message
    sessionStore.saveMessage(sessionId, "user", userPrompt);

    const agent = getAgent(session.agent);
    const availableTools = toolRegistry.getForAgent(session.agent);
    const toolSchemas = toolRegistry.toSchemas(availableTools);

    // Doom loop detection: track (toolName, argsHash) counts
    const doomTracker = new Map<string, number>();

    // Build message history for LLM
    const buildMessages = (): Message[] => sessionStore.getMessages(sessionId);

    let continueLoop = true;

    while (continueLoop && !controller.signal.aborted) {
      const messages = buildMessages();

      const pendingToolCalls: Array<{ id: string; name: string; input: unknown }> = [];
      const pendingToolResults: Array<{ id: string; output: string; metadata?: Record<string, unknown> }> = [];

      const stream = getProvider().stream({
        model: session.model,
        system: agent.systemPrompt,
        messages,
        tools: toolSchemas,
        signal: controller.signal,
      });

      let hasText = false;

      for await (const event of stream) {
        if (controller.signal.aborted) break;

        if (event.type === "text-delta" && event.text) {
          hasText = true;
          emit({ type: "text.delta", sessionID: sessionId, text: event.text });
        }

        if (event.type === "tool-call") {
          const { toolCallId, toolName, toolInput } = event;
          if (!toolCallId || !toolName) continue;

          // Doom loop check
          const key = `${toolName}:${JSON.stringify(toolInput)}`;
          const count = (doomTracker.get(key) ?? 0) + 1;
          doomTracker.set(key, count);
          if (count >= 3) {
            emit({
              type: "session.error",
              sessionID: sessionId,
              error: `Tool "${toolName}" called with identical args ${count} times — stopping to prevent infinite loop`,
            });
            continueLoop = false;
            break;
          }

          emit({ type: "tool.start", sessionID: sessionId, toolName, args: toolInput });

          const startMs = Date.now();
          const result = await toolRegistry.execute(toolName, toolInput, {
            sessionID: sessionId,
            workingDir,
            signal: controller.signal,
            emit,
          });
          const durationMs = Date.now() - startMs;

          emit({
            type: "tool.result",
            sessionID: sessionId,
            toolName,
            output: result.output,
            durationMs,
          });

          if (result.files?.length) {
            emit({ type: "session.diff", sessionID: sessionId, files: result.files });
          }

          pendingToolCalls.push({ id: toolCallId, name: toolName, input: toolInput });
          pendingToolResults.push({
            id: toolCallId,
            output: result.output,
            metadata: result.metadata,
          });
        }

        if (event.type === "finish") {
          if (hasText) {
            emit({ type: "text.done", sessionID: sessionId });
          }
          break;
        }

        if (event.type === "error") {
          emit({ type: "session.error", sessionID: sessionId, error: event.error ?? "Unknown error" });
          continueLoop = false;
          break;
        }
      }

      if (pendingToolCalls.length === 0) {
        // No tool calls — we're done
        continueLoop = false;
      } else {
        // Persist the tool exchange and loop
        const toolMessages = buildToolResultMessages(pendingToolCalls, pendingToolResults);
        for (const msg of toolMessages) {
          sessionStore.saveMessage(sessionId, msg.role as "user" | "assistant", msg.content);
        }
      }
    }
  } catch (err) {
    if (!controller.signal.aborted) {
      emit({
        type: "session.error",
        sessionID: sessionId,
        error: String(err),
      });
    }
  } finally {
    activeSessions.delete(sessionId);
    bus.emit({ type: "session.status", sessionID: sessionId, status: "idle" });
  }
}

export function interruptSession(sessionId: string): void {
  activeSessions.get(sessionId)?.abort();
  activeSessions.delete(sessionId);
}
