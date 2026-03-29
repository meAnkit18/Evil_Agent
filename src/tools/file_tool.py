"""
File Tool — pure Python file system operations (no shell needed).

Faster than CLI for simple file ops, and doesn't require a terminal.
"""

import os
import glob
import shutil
from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState


class FileTool(BaseTool):
    name = "file"
    description = (
        "Perform file system operations directly — read, write, search, copy, delete files. "
        "Faster than CLI for file tasks. Best for: reading configs, writing output, searching files."
    )
    actions = ["read", "write", "append", "delete", "copy", "move", "search", "exists"]

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            if action == "read":
                return self._read(args, state)
            elif action == "write":
                return self._write(args, state)
            elif action == "append":
                return self._append(args, state)
            elif action == "delete":
                return self._delete(args, state)
            elif action == "copy":
                return self._copy(args, state)
            elif action == "move":
                return self._move(args, state)
            elif action == "search":
                return self._search(args, state)
            elif action == "exists":
                return self._exists(args, state)
            else:
                return ToolResult.error(f"Unknown file action: {action}")
        except Exception as e:
            return ToolResult.fail(f"File tool error: {str(e)}")

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        valid, err = super().validate(action, args)
        if not valid:
            return valid, err

        if action in ("read", "delete", "exists") and "path" not in args:
            return False, "Missing required arg: 'path'"
        if action in ("write", "append") and ("path" not in args or "content" not in args):
            return False, "Missing required args: 'path' and 'content'"
        if action in ("copy", "move") and ("source" not in args or "destination" not in args):
            return False, "Missing required args: 'source' and 'destination'"
        if action == "search" and "pattern" not in args:
            return False, "Missing required arg: 'pattern'"

        return True, ""

    def _resolve(self, path: str, state: ExecutionState) -> str:
        # Expand ~ to user home directory
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            cwd = state.get("current_directory") or os.getcwd()
            return os.path.join(cwd, path)
        return path

    def _read(self, args: dict, state: ExecutionState) -> ToolResult:
        path = self._resolve(args["path"], state)
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}", retryable=False)

        with open(path, "r") as f:
            content = f.read()

        if len(content) > 10000:
            content = content[:10000] + "\n... [truncated]"

        return ToolResult.success(
            result=content,
            message=f"Read {os.path.basename(path)} ({len(content)} chars)",
            state_update={"last_output": content[:500]},
        )

    def _write(self, args: dict, state: ExecutionState) -> ToolResult:
        path = self._resolve(args["path"], state)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        with open(path, "w") as f:
            f.write(args["content"])

        return ToolResult.success(
            result=path,
            message=f"Wrote {os.path.basename(path)}",
            state_update={"last_output": f"File written: {path}"},
        )

    def _append(self, args: dict, state: ExecutionState) -> ToolResult:
        path = self._resolve(args["path"], state)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        with open(path, "a") as f:
            f.write(args["content"])

        return ToolResult.success(
            result=path,
            message=f"Appended to {os.path.basename(path)}",
        )

    def _delete(self, args: dict, state: ExecutionState) -> ToolResult:
        path = self._resolve(args["path"], state)
        if not os.path.exists(path):
            return ToolResult.fail(f"Not found: {path}", retryable=False)

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        return ToolResult.success(message=f"Deleted: {path}")

    def _copy(self, args: dict, state: ExecutionState) -> ToolResult:
        src = self._resolve(args["source"], state)
        dst = self._resolve(args["destination"], state)

        if not os.path.exists(src):
            return ToolResult.fail(f"Source not found: {src}", retryable=False)

        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)

        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

        return ToolResult.success(message=f"Copied {src} → {dst}")

    def _move(self, args: dict, state: ExecutionState) -> ToolResult:
        src = self._resolve(args["source"], state)
        dst = self._resolve(args["destination"], state)

        if not os.path.exists(src):
            return ToolResult.fail(f"Source not found: {src}", retryable=False)

        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.move(src, dst)

        return ToolResult.success(message=f"Moved {src} → {dst}")

    def _search(self, args: dict, state: ExecutionState) -> ToolResult:
        pattern = args["pattern"]
        directory = self._resolve(args.get("directory", "."), state)

        search_pattern = os.path.join(directory, "**", pattern)
        matches = glob.glob(search_pattern, recursive=True)

        # Limit results
        if len(matches) > 50:
            matches = matches[:50]

        return ToolResult.success(
            result=matches,
            message=f"Found {len(matches)} matches for '{pattern}'",
            state_update={"last_output": "\n".join(matches[:10])},
        )

    def _exists(self, args: dict, state: ExecutionState) -> ToolResult:
        path = self._resolve(args["path"], state)
        exists = os.path.exists(path)
        file_type = "directory" if os.path.isdir(path) else "file" if exists else "not found"

        return ToolResult.success(
            result={"exists": exists, "type": file_type, "path": path},
            message=f"{path}: {file_type}",
        )
