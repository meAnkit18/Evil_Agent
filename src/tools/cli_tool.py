"""
CLI Tool — wraps the existing terminal infrastructure as a unified tool.

Uses the existing PTYTerminal + CommandExecutor + CommandGuard.
"""

import os
import subprocess
from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState


class CLITool(BaseTool):
    name = "cli"
    description = (
        "Execute shell commands on the local system. "
        "Can run any CLI command, read files, write files, and manage the filesystem. "
        "Best for: system tasks, file operations, package management, git, and any terminal-based work."
    )
    actions = ["run_command", "read_file", "write_file", "list_dir"]

    def __init__(self):
        # Blocked commands for safety
        self._blocked_commands = {
            "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){", "fork bomb",
            "shutdown", "reboot", "halt", "poweroff", "init 0", "init 6",
        }

        # Interactive command → non-interactive equivalent
        self._sanitize_map = {
            "npm init": "npm init -y",
            "apt install": "apt install -y",
            "apt-get install": "apt-get install -y",
            "pip install": "pip install --no-input",
        }

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            if action == "run_command":
                return self._run_command(args, state)
            elif action == "read_file":
                return self._read_file(args, state)
            elif action == "write_file":
                return self._write_file(args, state)
            elif action == "list_dir":
                return self._list_dir(args, state)
            else:
                return ToolResult.error(f"Unknown action: {action}")
        except Exception as e:
            return ToolResult.error(f"CLI tool error: {str(e)}")

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        valid, err = super().validate(action, args)
        if not valid:
            return valid, err

        if action == "run_command":
            if "command" not in args:
                return False, "Missing required arg: 'command'"
        elif action == "read_file":
            if "path" not in args:
                return False, "Missing required arg: 'path'"
        elif action == "write_file":
            if "path" not in args or "content" not in args:
                return False, "Missing required args: 'path' and 'content'"
        elif action == "list_dir":
            pass  # path is optional (defaults to cwd)

        return True, ""

    # ─── Actions ─────────────────────────────────────────────────

    def _run_command(self, args: dict, state: ExecutionState) -> ToolResult:
        command = args["command"]
        cwd = args.get("cwd", state.get("current_directory") or os.getcwd())
        timeout = args.get("timeout", 30)

        # Safety check
        cmd_lower = command.lower().strip()
        for blocked in self._blocked_commands:
            if blocked in cmd_lower:
                return ToolResult.fail(
                    f"Command blocked for safety: contains '{blocked}'",
                    retryable=False,
                )

        # Sanitize interactive commands
        for pattern, replacement in self._sanitize_map.items():
            if pattern in command and "-y" not in command and "--yes" not in command:
                command = command.replace(pattern, replacement)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

            output = result.stdout.strip()
            error_output = result.stderr.strip()
            combined = output
            if error_output:
                combined += f"\n[STDERR]: {error_output}"

            # Truncate very long output
            if len(combined) > 5000:
                combined = combined[:5000] + "\n... [output truncated]"

            if result.returncode == 0:
                return ToolResult.success(
                    result=combined,
                    message=f"Command executed successfully (exit code 0)",
                    state_update={
                        "last_output": combined,
                        "current_directory": cwd,
                    },
                )
            else:
                return ToolResult.fail(
                    error=f"Command exited with code {result.returncode}: {combined}",
                    retryable=True,
                    result=combined,
                )

        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                f"Command timed out after {timeout}s: {command}",
                retryable=True,
            )

    def _read_file(self, args: dict, state: ExecutionState) -> ToolResult:
        path = args["path"]
        # Resolve relative paths from current directory
        if not os.path.isabs(path):
            cwd = state.get("current_directory") or os.getcwd()
            path = os.path.join(cwd, path)

        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}", retryable=False)

        try:
            with open(path, "r") as f:
                content = f.read()

            # Truncate very large files
            if len(content) > 10000:
                content = content[:10000] + "\n... [file truncated]"

            return ToolResult.success(
                result=content,
                message=f"Read {len(content)} chars from {path}",
                state_update={"last_output": content[:500]},
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to read {path}: {str(e)}")

    def _write_file(self, args: dict, state: ExecutionState) -> ToolResult:
        path = args["path"]
        content = args["content"]
        mode = args.get("mode", "w")  # 'w' for overwrite, 'a' for append

        if not os.path.isabs(path):
            cwd = state.get("current_directory") or os.getcwd()
            path = os.path.join(cwd, path)

        try:
            # Create parent directories
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, mode) as f:
                f.write(content)

            return ToolResult.success(
                result=path,
                message=f"Wrote {len(content)} chars to {path}",
                state_update={"last_output": f"File written: {path}"},
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to write {path}: {str(e)}")

    def _list_dir(self, args: dict, state: ExecutionState) -> ToolResult:
        path = args.get("path", state.get("current_directory") or os.getcwd())

        if not os.path.isabs(path):
            cwd = state.get("current_directory") or os.getcwd()
            path = os.path.join(cwd, path)

        if not os.path.isdir(path):
            return ToolResult.fail(f"Directory not found: {path}", retryable=False)

        try:
            entries = []
            for entry in sorted(os.listdir(path)):
                full_path = os.path.join(path, entry)
                entry_type = "dir" if os.path.isdir(full_path) else "file"
                size = os.path.getsize(full_path) if os.path.isfile(full_path) else None
                entries.append({
                    "name": entry,
                    "type": entry_type,
                    "size": size,
                })

            formatted = "\n".join(
                f"{'📁' if e['type'] == 'dir' else '📄'} {e['name']}"
                + (f" ({e['size']} bytes)" if e.get('size') else "")
                for e in entries
            )

            return ToolResult.success(
                result=entries,
                message=f"Listed {len(entries)} items in {path}",
                state_update={
                    "current_directory": path,
                    "last_output": formatted,
                },
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to list {path}: {str(e)}")
