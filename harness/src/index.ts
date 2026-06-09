// Load .env from harness directory
import { existsSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const envPath = join(__dirname, "..", ".env");

if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}

// Validate: need at least one provider key
const hasZen = !!process.env.ZEN_API_KEY;
const hasAnthropic = !!process.env.ANTHROPIC_API_KEY;

if (!hasZen && !hasAnthropic) {
  console.error("[harness] ERROR: Set ZEN_API_KEY or ANTHROPIC_API_KEY in harness/.env");
  process.exit(1);
}

const provider = hasZen ? "zen" : "anthropic";
const model = process.env.DEFAULT_MODEL ?? (hasZen ? "deepseek-v4-flash-free" : "claude-opus-4-8");

console.log(`[harness] Provider: ${provider}  Model: ${model}`);
process.env.ACTIVE_PROVIDER = provider;
process.env.DEFAULT_MODEL = model;

import { startServer } from "./server/server.ts";
startServer();
