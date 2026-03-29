"""
System Tool — lightweight system introspection.
"""

import os
import platform
from datetime import datetime
from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState


class SystemTool(BaseTool):
    name = "system"
    description = (
        "Get system information — OS details, running processes, environment variables, "
        "current time, disk usage. Best for: environment checks, system diagnostics."
    )
    actions = ["get_os_info", "get_env", "get_time", "check_command", "disk_usage"]

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            if action == "get_os_info":
                return self._os_info(args, state)
            elif action == "get_env":
                return self._get_env(args, state)
            elif action == "get_time":
                return self._get_time(args, state)
            elif action == "check_command":
                return self._check_command(args, state)
            elif action == "disk_usage":
                return self._disk_usage(args, state)
            else:
                return ToolResult.error(f"Unknown system action: {action}")
        except Exception as e:
            return ToolResult.fail(f"System tool error: {str(e)}")

    def _os_info(self, args: dict, state: ExecutionState) -> ToolResult:
        import shutil

        info = {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "cwd": os.getcwd(),
            "home": os.path.expanduser("~"),
        }

        state.update({"os_info": f"{info['os']} {info['os_release']}"})
        return ToolResult.success(
            result=info,
            message=f"{info['os']} {info['os_release']} ({info['machine']})",
            state_update={"os_info": f"{info['os']} {info['os_release']}"},
        )

    def _get_env(self, args: dict, state: ExecutionState) -> ToolResult:
        key = args.get("key")
        if key:
            value = os.environ.get(key)
            if value is None:
                return ToolResult.fail(f"Environment variable '{key}' not set", retryable=False)
            # Mask sensitive values
            if any(s in key.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                display = f"...{value[-4:]}" if len(value) > 4 else "****"
                return ToolResult.success(result=display, message=f"{key}={display}")
            return ToolResult.success(result=value, message=f"{key}={value}")
        else:
            # List all non-sensitive env vars
            safe_vars = {k: v for k, v in os.environ.items()
                         if not any(s in k.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"])}
            return ToolResult.success(
                result=safe_vars,
                message=f"{len(safe_vars)} environment variables",
            )

    def _get_time(self, args: dict, state: ExecutionState) -> ToolResult:
        now = datetime.now()
        return ToolResult.success(
            result=now.isoformat(),
            message=f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def _check_command(self, args: dict, state: ExecutionState) -> ToolResult:
        import shutil
        command = args.get("command", "")
        if not command:
            return ToolResult.fail("Missing 'command' arg", retryable=False)

        path = shutil.which(command)
        if path:
            return ToolResult.success(
                result={"available": True, "path": path},
                message=f"'{command}' found at {path}",
            )
        else:
            return ToolResult.success(
                result={"available": False, "path": None},
                message=f"'{command}' not found on PATH",
            )

    def _disk_usage(self, args: dict, state: ExecutionState) -> ToolResult:
        import shutil
        path = args.get("path", "/")
        try:
            usage = shutil.disk_usage(path)
            gb = lambda b: round(b / (1024**3), 2)
            info = {
                "total_gb": gb(usage.total),
                "used_gb": gb(usage.used),
                "free_gb": gb(usage.free),
                "percent_used": round((usage.used / usage.total) * 100, 1),
            }
            return ToolResult.success(
                result=info,
                message=f"Disk: {info['used_gb']}GB / {info['total_gb']}GB ({info['percent_used']}% used)",
            )
        except Exception as e:
            return ToolResult.fail(f"Disk usage check failed: {str(e)}")
