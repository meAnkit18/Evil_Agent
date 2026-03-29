"""
Shared Execution State — the single source of truth during task execution.

Every tool reads from and writes to this state. Steps are NOT isolated —
step 3 knows exactly what happened in step 1 because state carries forward.
"""

from __future__ import annotations
import copy
import threading
from datetime import datetime
from typing import Any, Optional


class ExecutionState:
    """
    Thread-safe shared state object that persists across all execution steps.
    
    This is what separates a real agent from a toy:
    - Every tool can read+write shared context
    - The planner/executor can see the full picture
    - Replanning has full context of what failed and why
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {
            # Environment
            "current_directory": None,
            "current_url": None,
            "os_info": None,

            # Session
            "logged_in": False,
            "session_started": datetime.now().isoformat(),

            # Execution tracking
            "last_output": None,
            "last_error": None,
            "last_tool_used": None,
            "last_action": None,

            # Step tracking
            "completed_steps": [],
            "failed_steps": [],
            "skipped_steps": [],

            # Error context
            "errors": [],
            "consecutive_failures": 0,

            # Custom data (tools can store anything here)
            "custom": {},
        }
        self._history: list[dict] = []  # snapshots for debugging

    # ─── Read ────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value by key."""
        with self._lock:
            # Support dotted keys: "custom.my_key"
            if "." in key:
                parts = key.split(".", 1)
                container = self._data.get(parts[0], {})
                if isinstance(container, dict):
                    return container.get(parts[1], default)
                return default
            return self._data.get(key, default)

    def snapshot(self) -> dict:
        """Return a frozen copy of the full state (for LLM context injection)."""
        with self._lock:
            return copy.deepcopy(self._data)

    # ─── Write ───────────────────────────────────────────────────

    def update(self, updates: dict):
        """
        Merge updates into state. Handles nested 'custom' dict.
        
        Usage:
            state.update({"current_url": "https://...", "logged_in": True})
            state.update({"custom.browser_cookies": [...]})
        """
        if not updates:
            return

        with self._lock:
            for key, value in updates.items():
                if "." in key:
                    parts = key.split(".", 1)
                    if parts[0] not in self._data:
                        self._data[parts[0]] = {}
                    if isinstance(self._data[parts[0]], dict):
                        self._data[parts[0]][parts[1]] = value
                else:
                    self._data[key] = value

    def set(self, key: str, value: Any):
        """Set a single state value."""
        self.update({key: value})

    # ─── Step Tracking ───────────────────────────────────────────

    def mark_completed(self, step_id: int, output: Any = None):
        """Record a successfully completed step."""
        with self._lock:
            self._data["completed_steps"].append({
                "step_id": step_id,
                "timestamp": datetime.now().isoformat(),
                "output": str(output)[:500] if output else None,
            })
            self._data["consecutive_failures"] = 0
            self._data["last_output"] = output

    def mark_failed(self, step_id: int, error: str):
        """Record a failed step."""
        with self._lock:
            self._data["failed_steps"].append({
                "step_id": step_id,
                "timestamp": datetime.now().isoformat(),
                "error": error,
            })
            self._data["errors"].append(error)
            self._data["consecutive_failures"] += 1
            self._data["last_error"] = error

            # Keep error list bounded
            if len(self._data["errors"]) > 20:
                self._data["errors"] = self._data["errors"][-20:]

    def mark_skipped(self, step_id: int, reason: str):
        """Record a skipped step."""
        with self._lock:
            self._data["skipped_steps"].append({
                "step_id": step_id,
                "reason": reason,
            })

    # ─── Queries ─────────────────────────────────────────────────

    def is_step_completed(self, step_id: int) -> bool:
        """Check if a step has been completed."""
        with self._lock:
            return any(s["step_id"] == step_id for s in self._data["completed_steps"])

    def completed_count(self) -> int:
        with self._lock:
            return len(self._data["completed_steps"])

    def failure_count(self) -> int:
        with self._lock:
            return len(self._data["failed_steps"])

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._data["consecutive_failures"]

    def get_step_result(self, step_id: int) -> Any:
        """Get the output result of a completed step by its ID."""
        with self._lock:
            for s in self._data["completed_steps"]:
                if s["step_id"] == step_id:
                    return s.get("output")
            return None

    def format_for_llm(self) -> str:
        """Format the state as a concise string for LLM context injection."""
        with self._lock:
            lines = ["## Current Execution State"]

            if self._data["current_directory"]:
                lines.append(f"- Working directory: {self._data['current_directory']}")
            if self._data["current_url"]:
                lines.append(f"- Current URL: {self._data['current_url']}")
            if self._data["logged_in"]:
                lines.append("- Login status: authenticated")

            completed = self._data["completed_steps"]
            if completed:
                lines.append(f"\n### Completed Steps ({len(completed)})")
                for s in completed[-5:]:  # last 5 only
                    output_preview = ""
                    if s.get("output"):
                        output_preview = f" → {s['output'][:100]}"
                    lines.append(f"- Step {s['step_id']}{output_preview}")

            failed = self._data["failed_steps"]
            if failed:
                lines.append(f"\n### Failed Steps ({len(failed)})")
                for s in failed[-3:]:
                    lines.append(f"- Step {s['step_id']}: {s['error'][:100]}")

            if self._data["last_output"]:
                preview = str(self._data["last_output"])[:200]
                lines.append(f"\n### Last Output\n{preview}")

            if self._data["last_error"]:
                lines.append(f"\n### Last Error\n{self._data['last_error'][:200]}")

            # Include page elements if available (from auto-inspect)
            custom = self._data.get("custom", {})
            if isinstance(custom, dict) and custom.get("page_elements"):
                lines.append(f"\n### Page Elements (auto-inspected — USE THESE SELECTORS)\n{custom['page_elements'][:2000]}")

            return "\n".join(lines)

    # ─── Reset ───────────────────────────────────────────────────

    def reset(self):
        """Reset all execution state for a new task."""
        with self._lock:
            # Save snapshot before reset
            self._history.append(copy.deepcopy(self._data))
            if len(self._history) > 5:
                self._history.pop(0)

            self._data["completed_steps"] = []
            self._data["failed_steps"] = []
            self._data["skipped_steps"] = []
            self._data["errors"] = []
            self._data["consecutive_failures"] = 0
            self._data["last_output"] = None
            self._data["last_error"] = None
            self._data["last_tool_used"] = None
            self._data["last_action"] = None
            self._data["session_started"] = datetime.now().isoformat()
