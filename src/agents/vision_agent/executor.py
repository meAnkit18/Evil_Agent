"""
Screen Executor — mouse + keyboard control via pyautogui.
Human-like mouse movement with safety bounds checking.
"""

import time
import random
import pyautogui

# Enable failsafe: move mouse to any corner to abort
pyautogui.FAILSAFE = True
# Default pause between pyautogui calls
pyautogui.PAUSE = 0.05


class ScreenExecutor:
    """
    Executes mouse and keyboard actions on the screen.
    Uses human-like movement patterns to avoid triggering anti-bot defenses.
    """

    def __init__(
        self,
        move_duration: float = 0.3,
        type_interval: float = 0.03,
        click_interval: float = 0.1,
    ):
        """
        Args:
            move_duration: Base duration for mouse movement (seconds)
            type_interval: Delay between keystrokes (seconds)
            click_interval: Delay between multi-clicks (seconds)
        """
        self.move_duration = move_duration
        self.type_interval = type_interval
        self.click_interval = click_interval
        self.screen_w, self.screen_h = pyautogui.size()

    def execute(self, action: dict) -> dict:
        """
        Execute a parsed action dict.

        Args:
            action: Validated action dict from the parser

        Returns:
            Result dict with status and message
        """
        action_type = action.get("action", "")

        try:
            if action_type == "click":
                return self._click(action)
            elif action_type == "double_click":
                return self._double_click(action)
            elif action_type == "right_click":
                return self._right_click(action)
            elif action_type == "type":
                return self._type(action)
            elif action_type == "hotkey":
                return self._hotkey(action)
            elif action_type == "scroll":
                return self._scroll(action)
            elif action_type == "drag":
                return self._drag(action)
            elif action_type == "wait":
                return self._wait(action)
            else:
                return {"status": "error", "message": f"Unknown action: {action_type}"}

        except pyautogui.FailSafeException:
            return {
                "status": "aborted",
                "message": "FAILSAFE triggered — mouse moved to screen corner",
            }
        except Exception as e:
            return {"status": "error", "message": f"Execution error: {str(e)}"}

    def _click(self, action: dict) -> dict:
        x, y = action["click_x"], action["click_y"]
        if not self._in_bounds(x, y):
            return {"status": "error", "message": f"Coordinates ({x}, {y}) out of bounds"}

        self._human_move(x, y)
        pyautogui.click(interval=self.click_interval)

        target = action.get("target", "unknown")
        return {"status": "success", "message": f"Clicked '{target}' at ({x}, {y})"}

    def _double_click(self, action: dict) -> dict:
        x, y = action["click_x"], action["click_y"]
        if not self._in_bounds(x, y):
            return {"status": "error", "message": f"Coordinates ({x}, {y}) out of bounds"}

        self._human_move(x, y)
        pyautogui.doubleClick(interval=self.click_interval)

        target = action.get("target", "unknown")
        return {"status": "success", "message": f"Double-clicked '{target}' at ({x}, {y})"}

    def _right_click(self, action: dict) -> dict:
        x, y = action["click_x"], action["click_y"]
        if not self._in_bounds(x, y):
            return {"status": "error", "message": f"Coordinates ({x}, {y}) out of bounds"}

        self._human_move(x, y)
        pyautogui.rightClick()

        target = action.get("target", "unknown")
        return {"status": "success", "message": f"Right-clicked '{target}' at ({x}, {y})"}

    def _type(self, action: dict) -> dict:
        text = action["text"]

        # Use write for regular text (faster, handles most chars)
        pyautogui.write(text, interval=self.type_interval)

        preview = text[:50] + ("..." if len(text) > 50 else "")
        return {"status": "success", "message": f"Typed: '{preview}'"}

    def _hotkey(self, action: dict) -> dict:
        keys = action["keys"]
        pyautogui.hotkey(*keys)

        combo = "+".join(keys)
        return {"status": "success", "message": f"Pressed: {combo}"}

    def _scroll(self, action: dict) -> dict:
        direction = action.get("direction", "down")
        amount = action.get("amount", 3)

        # Move to scroll target if bbox provided
        if "scroll_x" in action and "scroll_y" in action:
            self._human_move(action["scroll_x"], action["scroll_y"])

        clicks = amount if direction in ("down", "right") else -amount

        if direction in ("up", "down"):
            pyautogui.scroll(clicks)
        else:
            pyautogui.hscroll(clicks)

        return {"status": "success", "message": f"Scrolled {direction} by {amount}"}

    def _drag(self, action: dict) -> dict:
        fx, fy = action["from_x"], action["from_y"]
        tx, ty = action["to_x"], action["to_y"]

        if not self._in_bounds(fx, fy) or not self._in_bounds(tx, ty):
            return {"status": "error", "message": "Drag coordinates out of bounds"}

        self._human_move(fx, fy)
        duration = self.move_duration + random.uniform(0.1, 0.3)
        pyautogui.drag(tx - fx, ty - fy, duration=duration)

        target = action.get("target", "element")
        return {"status": "success", "message": f"Dragged '{target}' from ({fx},{fy}) to ({tx},{ty})"}

    def _wait(self, action: dict) -> dict:
        seconds = action.get("seconds", 2)
        time.sleep(seconds)
        return {"status": "success", "message": f"Waited {seconds}s"}

    def _human_move(self, x: int, y: int):
        """Move mouse with human-like speed variation."""
        # Add slight randomness to duration
        duration = self.move_duration + random.uniform(-0.05, 0.1)
        duration = max(0.1, duration)

        # Add tiny random offset (±2px) to avoid pixel-perfect detection
        jitter_x = random.randint(-2, 2)
        jitter_y = random.randint(-2, 2)
        target_x = max(0, min(x + jitter_x, self.screen_w - 1))
        target_y = max(0, min(y + jitter_y, self.screen_h - 1))

        pyautogui.moveTo(target_x, target_y, duration=duration, tween=pyautogui.easeOutQuad)

    def _in_bounds(self, x: int, y: int) -> bool:
        """Check if coordinates are within screen bounds."""
        return 0 <= x < self.screen_w and 0 <= y < self.screen_h
