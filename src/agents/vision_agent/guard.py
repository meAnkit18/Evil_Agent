"""
Safety Guard — validates actions before execution.
Kill switch, danger zone blocking, rate limiting, hotkey blacklist.
"""

import time
from typing import Dict, List, Set


class VisionGuard:
    """
    Safety layer between the planner and executor.
    Blocks dangerous actions and enforces rate limits.
    """

    def __init__(
        self,
        max_actions_per_second: float = 2.0,
        danger_zones: List[Dict] = None,
        hotkey_blacklist: List[tuple] = None,
    ):
        """
        Args:
            max_actions_per_second: Maximum action execution rate
            danger_zones: List of screen regions to block clicks on
            hotkey_blacklist: List of key combinations to block
        """
        self.max_actions_per_second = max_actions_per_second
        self.min_interval = 1.0 / max_actions_per_second
        self._last_action_time = 0.0
        self._action_count = 0
        self._repeated_actions: List[str] = []

        # Default danger zones (power buttons, system tray, etc.)
        self.danger_zones = danger_zones or []

        # Default hotkey blacklist — destructive key combinations
        self.hotkey_blacklist: Set[tuple] = set()
        default_blacklist = hotkey_blacklist or [
            ("ctrl", "alt", "delete"),
            ("ctrl", "alt", "del"),
            ("alt", "f4"),  # close window — only block if you want
            ("super", "l"),  # lock screen
        ]
        for combo in default_blacklist:
            self.hotkey_blacklist.add(tuple(sorted(k.lower() for k in combo)))

        # Runaway detection
        self._max_repeated = 5  # max same action in a row

    def check_action(self, action: dict) -> Dict:
        """
        Validate an action before execution.

        Returns:
            {"status": "allowed"} or {"status": "blocked", "reason": "..."}
        """
        action_type = action.get("action", "")

        # --- Rate Limiting ---
        now = time.time()
        elapsed = now - self._last_action_time
        if elapsed < self.min_interval:
            return {
                "status": "blocked",
                "reason": f"Rate limit: {elapsed:.2f}s since last action (min {self.min_interval:.2f}s)",
            }

        # --- Action Validation ---
        if not action_type:
            return {"status": "blocked", "reason": "No action type specified"}

        # --- Danger Zone Check (for coordinate-based actions) ---
        if action_type in ("click", "double_click", "right_click"):
            x = action.get("click_x")
            y = action.get("click_y")
            if x is not None and y is not None:
                for zone in self.danger_zones:
                    zx1, zy1 = zone.get("x1", 0), zone.get("y1", 0)
                    zx2, zy2 = zone.get("x2", 0), zone.get("y2", 0)
                    if zx1 <= x <= zx2 and zy1 <= y <= zy2:
                        return {
                            "status": "blocked",
                            "reason": f"Click at ({x},{y}) is in danger zone: {zone.get('name', 'unnamed')}",
                        }

        # --- Hotkey Blacklist ---
        if action_type == "hotkey":
            keys = action.get("keys", [])
            normalized = tuple(sorted(k.lower() for k in keys))
            if normalized in self.hotkey_blacklist:
                combo = "+".join(keys)
                return {
                    "status": "blocked",
                    "reason": f"Hotkey '{combo}' is blacklisted (destructive)",
                }

        # --- Runaway Detection ---
        action_sig = self._action_signature(action)
        if self._repeated_actions and self._repeated_actions[-1] == action_sig:
            repeat_count = sum(
                1 for a in self._repeated_actions if a == action_sig
            )
            if repeat_count >= self._max_repeated:
                return {
                    "status": "blocked",
                    "reason": f"Same action repeated {repeat_count} times — possible infinite loop",
                }

        # --- All Clear ---
        self._last_action_time = now
        self._action_count += 1
        self._repeated_actions.append(action_sig)
        # Keep only last 10
        if len(self._repeated_actions) > 10:
            self._repeated_actions.pop(0)

        return {"status": "allowed"}

    def _action_signature(self, action: dict) -> str:
        """Create a signature string for an action (for dedup detection)."""
        parts = [action.get("action", "")]

        if "click_x" in action:
            # Bucket coordinates to 20px grid to detect "same area" clicks
            bx = (action["click_x"] // 20) * 20
            by = (action["click_y"] // 20) * 20
            parts.append(f"{bx},{by}")

        if "text" in action:
            parts.append(action["text"][:20])

        if "keys" in action:
            parts.append("+".join(action["keys"]))

        return "|".join(parts)

    def add_danger_zone(self, name: str, x1: int, y1: int, x2: int, y2: int):
        """Add a screen region where clicks are blocked."""
        self.danger_zones.append({
            "name": name,
            "x1": x1, "y1": y1,
            "x2": x2, "y2": y2,
        })

    def reset(self):
        """Reset all tracking state."""
        self._last_action_time = 0.0
        self._action_count = 0
        self._repeated_actions.clear()
