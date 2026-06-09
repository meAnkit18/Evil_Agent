import { z } from "zod";
import type { ToolDef } from "./tool.ts";

const moveParams = z.object({
  x: z.number().describe("X coordinate in pixels"),
  y: z.number().describe("Y coordinate in pixels"),
});

const clickParams = z.object({
  x: z.number().describe("X coordinate to click"),
  y: z.number().describe("Y coordinate to click"),
  button: z.enum(["left", "right", "middle"]).optional().default("left"),
  double: z.boolean().optional().default(false).describe("Double-click"),
});

async function getNut() {
  const { mouse, Button, straightTo, Point } = await import("@nut-tree-fork/nut-js");
  return { mouse, Button, straightTo, Point };
}

export const mouseMoveTool: ToolDef<z.infer<typeof moveParams>> = {
  name: "mouse_move",
  description: "Move the mouse cursor to a screen position.",
  parameters: moveParams,
  permission: "auto",

  async execute({ x, y }) {
    const { mouse, straightTo, Point } = await getNut();
    await mouse.move(straightTo(new Point(x, y)));
    return { output: `Moved mouse to (${x}, ${y})` };
  },
};

export const mouseClickTool: ToolDef<z.infer<typeof clickParams>> = {
  name: "mouse_click",
  description: "Click the mouse at a screen position.",
  parameters: clickParams,
  permission: "ask_once",

  async execute({ x, y, button, double }) {
    const { mouse, Button, straightTo, Point } = await getNut();
    const btn =
      button === "right" ? Button.RIGHT : button === "middle" ? Button.MIDDLE : Button.LEFT;

    await mouse.move(straightTo(new Point(x, y)));
    if (double) {
      await mouse.doubleClick(btn);
    } else {
      await mouse.click(btn);
    }
    return { output: `Clicked ${button} at (${x}, ${y})${double ? " (double)" : ""}` };
  },
};
