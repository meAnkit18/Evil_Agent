import re


class CommandGuard:
    def __init__(self):
        # Hard blocked commands (you can expand later)
        self.blocked_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-rf\s+\*",
            r":\(\)\s*\{\s*:\|\:&\s*\};:",  # fork bomb
            r"shutdown",
            r"reboot",
            r"mkfs",
            r"dd\s+if=",
            r">\s*/dev/sd",
        ]

    def is_safe(self, command: str) -> bool:
        command = command.strip().lower()

        for pattern in self.blocked_patterns:
            if re.search(pattern, command):
                return False

        return True

    def check(self, command: str) -> dict:
        if not self.is_safe(command):
            return {
                "status": "blocked",
                "reason": "Command blocked for safety",
                "command": command,
            }

        return {
            "status": "allowed",
            "command": command,
        }