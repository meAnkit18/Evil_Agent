"""
Session Memory — stores action history for LLM context.
Tracks step-by-step log with coordinates, confidence, and verification status.
"""

from typing import List, Dict, Optional


class SessionMemory:
    """
    Sliding-window memory of executed actions and their results.
    Formatted as concise text for VLM context.
    """

    def __init__(self, max_steps: int = 10):
        self.history: List[Dict] = []
        self.max_steps = max_steps

    def add(
        self,
        step: int,
        action: dict,
        result: dict,
        verification: dict = None,
    ):
        """
        Record a completed action step.

        Args:
            step: Step number
            action: The action dict (action type, coords, confidence, etc.)
            result: The execution result (status, message)
            verification: Optional verification result (success, evidence)
        """
        entry = {
            "step": step,
            "reasoning": action.get("reasoning", action.get("thought", "")),
            "action": action.get("action", action.get("status", "unknown")),
            "confidence": action.get("confidence", 0.0),
            "result_status": result.get("status", "unknown"),
            "result_message": result.get("message", "")[:200],
        }

        # Coordinate info
        if "click_x" in action:
            entry["coords"] = (action["click_x"], action["click_y"])
        if "bbox" in action:
            entry["bbox"] = action["bbox"]

        # Target name
        if "target" in action:
            entry["target"] = action["target"][:100]

        # Text typed
        if "text" in action:
            entry["text"] = action["text"][:80]

        # Keys pressed
        if "keys" in action:
            entry["keys"] = "+".join(action["keys"])

        # Verification
        if verification:
            entry["verified"] = verification.get("success", None)
            entry["evidence"] = verification.get("evidence", "")[:150]

        self.history.append(entry)

        # Sliding window
        if len(self.history) > self.max_steps:
            self.history.pop(0)

    def format_for_llm(self) -> str:
        """Format history as a concise text block for VLM context."""
        if not self.history:
            return "(no previous actions)"

        lines = []
        for entry in self.history:
            step = entry["step"]
            action = entry["action"]
            status = entry["result_status"]
            conf = entry.get("confidence", 0.0)

            line = f"Step {step}: {action}"

            if "target" in entry:
                line += f' "{entry["target"]}"'
            if "coords" in entry:
                cx, cy = entry["coords"]
                line += f" at ({cx},{cy})"
            if "text" in entry:
                line += f' text="{entry["text"]}"'
            if "keys" in entry:
                line += f" keys={entry['keys']}"

            line += f" → {status} (conf={conf:.2f})"

            if "verified" in entry:
                v = "✓" if entry["verified"] else "✗"
                line += f" [verified={v}]"
                if entry.get("evidence"):
                    line += f" ({entry['evidence']})"

            lines.append(line)

        return "\n".join(lines)

    def get_last(self) -> Dict:
        """Get the most recent entry."""
        return self.history[-1] if self.history else {}

    def get_success_rate(self) -> float:
        """Calculate the success rate of recent actions."""
        if not self.history:
            return 0.0
        successes = sum(
            1 for e in self.history if e["result_status"] == "success"
        )
        return successes / len(self.history)

    def clear(self):
        """Clear all history."""
        self.history.clear()
