"""
Vision Tool — wraps the existing vision agent executor for pixel-based desktop control.

Uses the existing ScreenExecutor + ScreenCapture from vision_agent.
"""

from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState


class VisionTool(BaseTool):
    name = "vision"
    description = (
        "Control the desktop through pixel-based screen interaction. "
        "Click anywhere on screen, type text, use hotkeys, scroll, take screenshots. "
        "Best for: desktop apps, GUI automation, anything not in a browser."
    )
    actions = [
        "click_screen", "double_click", "right_click",
        "type_text", "hotkey", "scroll", "screenshot", "wait",
    ]

    def __init__(self, move_duration: float = 0.3):
        self._executor = None
        self._screen = None
        self._move_duration = move_duration
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-init to avoid importing pyautogui on headless systems."""
        if self._initialized:
            return

        try:
            from agents.vision_agent.executor import ScreenExecutor
            from agents.vision_agent.screen import ScreenCapture

            self._executor = ScreenExecutor(move_duration=self._move_duration)
            self._screen = ScreenCapture()
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Vision dependencies not available: {e}")

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            self._ensure_initialized()

            if action == "click_screen":
                return self._click(args, state)
            elif action == "double_click":
                return self._double_click(args, state)
            elif action == "right_click":
                return self._right_click(args, state)
            elif action == "type_text":
                return self._type_text(args, state)
            elif action == "hotkey":
                return self._hotkey(args, state)
            elif action == "scroll":
                return self._scroll(args, state)
            elif action == "screenshot":
                return self._screenshot(args, state)
            elif action == "wait":
                return self._wait(args, state)
            else:
                return ToolResult.error(f"Unknown vision action: {action}")

        except Exception as e:
            return ToolResult.fail(f"Vision tool error: {str(e)}", retryable=True)

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        valid, err = super().validate(action, args)
        if not valid:
            return valid, err

        if action in ("click_screen", "double_click", "right_click"):
            if "click_x" not in args or "click_y" not in args:
                return False, "Missing required args: 'click_x' and 'click_y'"
        if action == "type_text" and "text" not in args:
            return False, "Missing required arg: 'text'"
        if action == "hotkey" and "keys" not in args:
            return False, "Missing required arg: 'keys'"

        return True, ""

    # ─── Actions ─────────────────────────────────────────────────

    def _click(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {"action": "click", **args}
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _double_click(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {"action": "double_click", **args}
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _right_click(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {"action": "right_click", **args}
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _type_text(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {"action": "type", "text": args["text"]}
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _hotkey(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {"action": "hotkey", "keys": args["keys"]}
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _scroll(self, args: dict, state: ExecutionState) -> ToolResult:
        action = {
            "action": "scroll",
            "direction": args.get("direction", "down"),
            "amount": args.get("amount", 3),
        }
        if "scroll_x" in args:
            action["scroll_x"] = args["scroll_x"]
            action["scroll_y"] = args["scroll_y"]
        result = self._executor.execute(action)
        return self._wrap_result(result, state)

    def _screenshot(self, args: dict, state: ExecutionState) -> ToolResult:
        path = args.get("path", "/tmp/vision_screenshot.png")
        try:
            img = self._screen.capture_full()
            img.save(path)
            return ToolResult.success(
                result=path,
                message=f"Screenshot saved to {path}",
                state_update={"custom.last_screenshot": path},
            )
        except Exception as e:
            return ToolResult.fail(f"Screenshot failed: {str(e)}")

    def _wait(self, args: dict, state: ExecutionState) -> ToolResult:
        import time
        seconds = args.get("seconds", 2)
        time.sleep(seconds)
        return ToolResult.success(message=f"Waited {seconds}s")

    # ─── Helpers ─────────────────────────────────────────────────

    def _wrap_result(self, result: dict, state: ExecutionState) -> ToolResult:
        """Convert old-style executor result dict to ToolResult."""
        if result.get("status") == "success":
            return ToolResult.success(
                message=result.get("message", ""),
                state_update={"last_output": result.get("message", "")},
            )
        elif result.get("status") == "aborted":
            return ToolResult.fail(
                result.get("message", "Action aborted"),
                retryable=False,
            )
        else:
            return ToolResult.fail(
                result.get("message", "Action failed"),
                retryable=True,
            )
