import { app, BrowserWindow, ipcMain } from "electron";
import path from "path";
import { spawn, type ChildProcess } from "child_process";

const HARNESS_PORT = 7777;
const HARNESS_URL = `http://127.0.0.1:${HARNESS_PORT}`;
const HARNESS_ENTRY = path.resolve(__dirname, "../../harness/src/index.ts");

let harnessProcess: ChildProcess | null = null;

function spawnHarness(): void {
  if (harnessProcess) return;

  harnessProcess = spawn("bun", ["run", HARNESS_ENTRY], {
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });

  harnessProcess.stdout?.on("data", (d) => process.stdout.write(`[harness] ${d}`));
  harnessProcess.stderr?.on("data", (d) => process.stderr.write(`[harness] ${d}`));

  harnessProcess.on("exit", (code) => {
    console.log(`[main] harness exited with code ${code}`);
    harnessProcess = null;
  });
}

async function waitForHarness(maxAttempts = 30): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const r = await fetch(`${HARNESS_URL}/health`);
      if (r.ok) return true;
    } catch { /* not ready yet */ }
    await new Promise((res) => setTimeout(res, 1000));
  }
  return false;
}

async function createWindow(): Promise<void> {
  // Spawn harness first
  spawnHarness();

  const ready = await waitForHarness();
  if (!ready) {
    console.error("[main] harness failed to start — continuing anyway");
  }

  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    fullscreen: true,
    transparent: true,
    frame: false,
    hasShadow: false,
    alwaysOnTop: true,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "renderer/index.html"));

  ipcMain.on("close-window", () => win.close());
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  harnessProcess?.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  harnessProcess?.kill();
});
