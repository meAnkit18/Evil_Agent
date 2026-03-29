"""
Action Planner — decision layer between VLM output and executor.
Confidence gating, multi-step decomposition, stuck detection.
"""

from typing import Optional, List, Dict


class ActionPlanner:
    """
    Evaluates VLM actions before execution.
    Gates by confidence, tracks retries, detects stuck states.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        max_retries_per_action: int = 3,
        stuck_threshold: int = 3,
    ):
        """
        Args:
            confidence_threshold: Minimum confidence to execute (0.0-1.0)
            max_retries_per_action: Max retries before forcing new strategy
            stuck_threshold: Same action N times → force different approach
        """
        self.confidence_threshold = confidence_threshold
        self.max_retries_per_action = max_retries_per_action
        self.stuck_threshold = stuck_threshold

        self._retry_count: Dict[str, int] = {}
        self._recent_actions: List[str] = []
        self._step_queue: List[dict] = []

    def evaluate(self, action: dict) -> dict:
        """
        Evaluate whether to execute, retry, or reject an action.

        Args:
            action: Parsed action dict from the parser

        Returns:
            One of:
                {"decision": "execute", "action": action}
                {"decision": "retry", "reason": "..."}
                {"decision": "reject", "reason": "..."}
        """
        # Pass through completion/error status
        if action.get("status") in ("done", "error"):
            return {"decision": "execute", "action": action}

        # Parse errors from the parser
        if action.get("status") == "error" and "reason" in action:
            return {"decision": "retry", "reason": f"Parse error: {action['reason']}"}

        action_type = action.get("action", "")
        confidence = action.get("confidence", 0.0)

        # --- Confidence Gate ---
        if confidence < self.confidence_threshold:
            return {
                "decision": "retry",
                "reason": f"Low confidence ({confidence:.2f} < {self.confidence_threshold})",
            }

        # --- Stuck Detection ---
        action_sig = self._signature(action)
        consecutive = self._count_consecutive(action_sig)

        if consecutive >= self.stuck_threshold:
            self._recent_actions.clear()
            return {
                "decision": "reject",
                "reason": f"Stuck: same action '{action_type}' repeated {consecutive}x — need different approach",
            }

        # --- Retry Budget ---
        retry_key = action_sig
        retries = self._retry_count.get(retry_key, 0)
        if retries >= self.max_retries_per_action:
            self._retry_count[retry_key] = 0
            return {
                "decision": "reject",
                "reason": f"Max retries ({self.max_retries_per_action}) exceeded for this action",
            }

        # --- Approved ---
        self._recent_actions.append(action_sig)
        if len(self._recent_actions) > 20:
            self._recent_actions.pop(0)

        return {"decision": "execute", "action": action}

    def record_failure(self, action: dict):
        """Record a failed action to track retries."""
        sig = self._signature(action)
        self._retry_count[sig] = self._retry_count.get(sig, 0) + 1

    def record_success(self, action: dict):
        """Record a successful action — reset retry count."""
        sig = self._signature(action)
        self._retry_count.pop(sig, None)

    def _signature(self, action: dict) -> str:
        """Create a fingerprint for action dedup tracking."""
        parts = [action.get("action", "")]

        if "click_x" in action:
            # 30px grid bucket
            bx = (action["click_x"] // 30) * 30
            by = (action["click_y"] // 30) * 30
            parts.append(f"@{bx},{by}")

        if "text" in action:
            parts.append(f"t:{action['text'][:20]}")

        if "keys" in action:
            parts.append(f"k:{'+'.join(action['keys'])}")

        return "|".join(parts)

    def _count_consecutive(self, sig: str) -> int:
        """Count how many times the latest action was the same."""
        count = 0
        for s in reversed(self._recent_actions):
            if s == sig:
                count += 1
            else:
                break
        return count

    def reset(self):
        """Reset all planner state."""
        self._retry_count.clear()
        self._recent_actions.clear()
        self._step_queue.clear()
