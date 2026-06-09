import { z } from "zod";
import type { ToolDef } from "./tool.ts";

const typeParams = z.object({
  text: z.string().describe("Text to type"),
});

const keyParams = z.object({
  key: z
    .string()
    .describe(
      "Key or key combo to press, e.g. 'Return', 'ctrl+c', 'alt+Tab', 'ctrl+shift+t'"
    ),
});

async function getNut() {
  const { keyboard, Key } = await import("@nut-tree-fork/nut-js");
  return { keyboard, Key };
}

export const typeTextTool: ToolDef<z.infer<typeof typeParams>> = {
  name: "type_text",
  description: "Type text using the keyboard.",
  parameters: typeParams,
  permission: "ask_once",

  async execute({ text }) {
    const { keyboard } = await getNut();
    await keyboard.type(text);
    return { output: `Typed: ${text.slice(0, 80)}${text.length > 80 ? "..." : ""}` };
  },
};

export const keyPressTool: ToolDef<z.infer<typeof keyParams>> = {
  name: "key_press",
  description:
    "Press a key or key combination. Examples: 'Return', 'ctrl+c', 'alt+Tab', 'ctrl+shift+t'.",
  parameters: keyParams,
  permission: "ask_once",

  async execute({ key }) {
    const { keyboard, Key } = await getNut();

    const parts = key.toLowerCase().split("+");
    const modifiers: unknown[] = [];
    let mainKey: unknown = null;

    const modMap: Record<string, unknown> = {
      ctrl: Key.LeftControl,
      control: Key.LeftControl,
      alt: Key.LeftAlt,
      shift: Key.LeftShift,
      super: Key.LeftSuper,
      win: Key.LeftSuper,
      cmd: Key.LeftSuper,
    };

    for (const part of parts) {
      if (modMap[part]) {
        modifiers.push(modMap[part]);
      } else {
        const mapped = mapKey(part, Key);
        if (mapped) mainKey = mapped;
      }
    }

    if (!mainKey) {
      return { output: `Error: unknown key "${key}"` };
    }

    if (modifiers.length > 0) {
      await keyboard.pressKey(...(modifiers as Parameters<typeof keyboard.pressKey>), mainKey as never);
      await keyboard.releaseKey(...(modifiers as Parameters<typeof keyboard.releaseKey>), mainKey as never);
    } else {
      await keyboard.pressKey(mainKey as never);
      await keyboard.releaseKey(mainKey as never);
    }

    return { output: `Pressed: ${key}` };
  },
};

function mapKey(name: string, Key: Record<string, unknown>): unknown {
  const direct: Record<string, string> = {
    return: "Return",
    enter: "Return",
    escape: "Escape",
    esc: "Escape",
    tab: "Tab",
    space: "Space",
    backspace: "Backspace",
    delete: "Delete",
    del: "Delete",
    home: "Home",
    end: "End",
    pageup: "PageUp",
    pagedown: "PageDown",
    up: "Up",
    down: "Down",
    left: "Left",
    right: "Right",
    f1: "F1", f2: "F2", f3: "F3", f4: "F4",
    f5: "F5", f6: "F6", f7: "F7", f8: "F8",
    f9: "F9", f10: "F10", f11: "F11", f12: "F12",
  };

  const mapped = direct[name.toLowerCase()];
  if (mapped && Key[mapped] !== undefined) return Key[mapped];

  // Single character — use uppercase key name
  if (name.length === 1) {
    const upper = name.toUpperCase();
    if (Key[upper] !== undefined) return Key[upper];
  }

  return null;
}
