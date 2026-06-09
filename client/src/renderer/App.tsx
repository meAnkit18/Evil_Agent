import React, { useEffect } from "react";
import { useHarness } from "./useHarness";
import { ChatArea } from "./components/ChatArea";
import { PromptBar } from "./components/PromptBar";
import { Sidebar } from "./components/Sidebar";
import { ToolActivity } from "./components/ToolActivity";
import { PermissionOverlay } from "./components/PermissionOverlay";

export function App() {
  const {
    connected,
    status,
    messages,
    activeTool,
    pendingPermission,
    sendPrompt,
    interrupt,
    grantPermission,
  } = useHarness();

  // Double-ESC closes the app
  useEffect(() => {
    let lastEsc = 0;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        const now = Date.now();
        if (now - lastEsc < 500) window.electronAPI?.closeWindow();
        lastEsc = now;
      }
      if (e.ctrlKey && e.key === "x") {
        window.electronAPI?.closeWindow();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="overlay">
      <ChatArea messages={messages} status={status} />

      <ToolActivity tool={activeTool} status={status} />

      <PromptBar onSubmit={sendPrompt} disabled={status === "busy"} />

      <Sidebar
        connected={connected}
        status={status}
        onInterrupt={interrupt}
      />

      {pendingPermission && (
        <PermissionOverlay
          toolName={pendingPermission.toolName}
          args={pendingPermission.args}
          description={pendingPermission.description}
          onAllow={() => grantPermission(true)}
          onDeny={() => grantPermission(false)}
        />
      )}
    </div>
  );
}

// Extend window with Electron API type
declare global {
  interface Window {
    electronAPI?: {
      closeWindow: () => void;
    };
  }
}
