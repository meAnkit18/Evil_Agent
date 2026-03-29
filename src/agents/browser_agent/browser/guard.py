"""
Safety Guard — validates actions and URLs before execution.
Blocks dangerous navigations and malformed actions.
"""

import re
from urllib.parse import urlparse


class BrowserGuard:
    """Safety layer for browser actions."""

    def __init__(self):
        # Blocked URL patterns
        self.blocked_url_patterns = [
            r"^file://",
            r"^javascript:",
            r"^data:",
            r"^chrome://",
            r"^chrome-extension://",
            r"^about:",
        ]

        # Blocked IP ranges (internal networks)
        self.blocked_hosts = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.",  # link-local
        ]

        # Valid action types
        self.valid_actions = {
            "click", "type", "scroll", "wait",
            "navigate", "select", "done"
        }

        # Required fields per action
        self.required_fields = {
            "click": ["element_id"],
            "type": ["element_id", "text"],
            "scroll": [],
            "wait": [],
            "navigate": ["url"],
            "select": ["element_id", "value"],
            "done": [],
        }

    def check_action(self, action: dict) -> dict:
        """
        Validate an action before execution.
        Returns: {"status": "allowed"|"blocked", "reason": "..."}
        """
        action_type = action.get("action", "").lower()

        # Check if it's a done status
        if action.get("status") == "done":
            return {"status": "allowed"}

        # Validate action type
        if action_type not in self.valid_actions:
            return {
                "status": "blocked",
                "reason": f"Unknown action type: {action_type}"
            }

        # Validate required fields
        required = self.required_fields.get(action_type, [])
        for field in required:
            if field not in action or action[field] is None:
                return {
                    "status": "blocked",
                    "reason": f"Missing required field '{field}' for {action_type}"
                }

        # URL safety check for navigate
        if action_type == "navigate":
            url_check = self.check_url(action.get("url", ""))
            if url_check["status"] == "blocked":
                return url_check

        return {"status": "allowed"}

    def check_url(self, url: str) -> dict:
        """Check if a URL is safe to navigate to."""
        url = url.strip()

        # Check blocked URL schemes
        for pattern in self.blocked_url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return {
                    "status": "blocked",
                    "reason": f"Blocked URL scheme: {url[:30]}"
                }

        # Parse and check host
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""

            for blocked in self.blocked_hosts:
                if host == blocked or host.startswith(blocked):
                    return {
                        "status": "blocked",
                        "reason": f"Blocked host: {host}"
                    }

            # Check for private IP ranges
            if re.match(r"^10\.", host) or re.match(r"^192\.168\.", host):
                return {
                    "status": "blocked",
                    "reason": f"Blocked private IP: {host}"
                }

        except Exception:
            pass  # If we can't parse, let it through — Playwright will handle errors

        return {"status": "allowed"}
