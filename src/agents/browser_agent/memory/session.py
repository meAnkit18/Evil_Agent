"""
Session Memory — stores action history for LLM context.
Mirrors the CLI agent's SessionMemory with browser-specific fields.
"""

from typing import List, Dict


class SessionMemory:
    def __init__(self, max_steps: int = 8):
        self.history: List[Dict] = []
        self.max_steps = max_steps

    def add(self, step: int, action: dict, result: dict):
        """
        Record a completed action and its result.

        Args:
            step: Step number
            action: The action dict (thought, action, element_id, etc.)
            result: The execution result (status, message, url)
        """
        entry = {
            "step": step,
            "thought": action.get("thought", ""),
            "action": action.get("action", action.get("status", "unknown")),
            "result_status": result.get("status", "unknown"),
            "result_message": result.get("message", "")[:300],  # truncate
            "url_after": result.get("url", ""),
        }

        # Include action-specific details
        if "element_id" in action:
            entry["element_id"] = action["element_id"]
        if "text" in action:
            # Mask credentials
            text = action["text"]
            if "__CREDENTIAL_" in text:
                text = "[CREDENTIAL]"
            entry["text"] = text[:100]
        if "url" in action:
            entry["target_url"] = action["url"]

        self.history.append(entry)

        # Keep only last N steps
        if len(self.history) > self.max_steps:
            self.history.pop(0)

    def format_for_llm(self) -> str:
        """Format history as a readable string for LLM context."""
        if not self.history:
            return "(no previous actions)"

        lines = []
        for entry in self.history:
            step = entry["step"]
            action = entry["action"]
            status = entry["result_status"]
            message = entry["result_message"]
            thought = entry.get("thought", "")

            line = f"Step {step}: {action}"
            if "element_id" in entry:
                line += f" [element {entry['element_id']}]"
            if "text" in entry:
                line += f' text="{entry["text"]}"'
            if "target_url" in entry:
                line += f" → {entry['target_url']}"

            line += f" → {status}"
            if message:
                line += f" ({message})"

            lines.append(line)

        return "\n".join(lines)

    def get_last_action(self) -> Dict:
        """Get the most recent action entry."""
        return self.history[-1] if self.history else {}

    def clear(self):
        """Clear all history."""
        self.history.clear()
