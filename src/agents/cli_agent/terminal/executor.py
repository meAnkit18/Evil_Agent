from typing import Dict
from agents.cli_agent.terminal.pty_terminal import PTYTerminal
from agents.cli_agent.terminal.guard import CommandGuard


class CommandExecutor:
    def __init__(self, terminal: PTYTerminal, guard: CommandGuard):
        self.terminal = terminal
        self.guard = guard

        # Map interactive commands to their non-interactive equivalents
        self.interactive_map = {
            "npx create-vite": "npx create-vite@latest . --yes",
            "npm init": "npm init -y",
            "apt install": "apt install -y",
            "apt-get install": "apt-get install -y",
        }

    def execute(self, command: str) -> Dict:
        """
        Main execution pipeline:
        - sanitize interactive commands
        - validate command
        - run in terminal
        - classify result
        """

        # Step 1: Sanitize interactive commands
        command = self._sanitize_command(command)

        # Step 2: Guard check
        guard_result = self.guard.check(command)

        if guard_result["status"] == "blocked":
            return {
                "status": "blocked",
                "command": command,
                "output": "",
                "error": guard_result["reason"]
            }

        # Step 3: Execute command
        try:
            result = self.terminal.run(command)
            output = result.get("output", "")

            # Step 4: classify success/failure
            status = self._classify(output)

            return {
                "status": status,
                "command": command,
                "output": output,
                "error": None if status == "success" else "Command may have failed"
            }

        except Exception as e:
            return {
                "status": "error",
                "command": command,
                "output": "",
                "error": str(e)
            }

    def _sanitize_command(self, command: str) -> str:
        """
        Replace known interactive commands with non-interactive equivalents.
        Prevents the agent from getting stuck on prompts.
        """
        for pattern, replacement in self.interactive_map.items():
            if pattern in command:
                return command.replace(pattern, replacement)

        return command

    def _classify(self, output: str) -> str:
        """
        Classify command output as success or error.
        Uses both error and success keyword matching.
        """
        output_lower = output.lower()

        error_keywords = [
            "error",
            "failed",
            "not found",
            "permission denied",
            "no such file",
            "command not found",
            "traceback",
            "exception",
            "fatal",
            "abort",
        ]

        success_keywords = [
            "created",
            "success",
            "added",
            "installed",
            "done",
            "written",
            "copied",
            "moved",
            "removed",
            "updated",
        ]

        has_error = any(e in output_lower for e in error_keywords)
        has_success = any(s in output_lower for s in success_keywords)

        # If both present, error takes priority
        if has_error and not has_success:
            return "error"

        if has_success:
            return "success"

        # Fallback: no strong signal → treat as success
        return "success"