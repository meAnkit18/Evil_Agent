"""
Action Engine — executes structured actions on indexed elements.
Handles click, type, scroll, wait, navigate.
Performs credential token substitution.
Re-extracts DOM after every action.
"""

from typing import Optional


class ActionEngine:
    """Execute browser actions using element IDs from the indexer."""

    def __init__(self, controller, indexer, credentials: Optional[dict] = None):
        self.controller = controller
        self.indexer = indexer
        self.credentials = credentials or {}

    async def execute(self, action: dict) -> dict:
        """
        Execute a structured action dict.
        Returns: {"status": "success"|"error", "message": "...", "url": "..."}
        """
        action_type = action.get("action", "").lower()

        try:
            if action_type == "click":
                return await self._click(action)
            elif action_type == "type":
                return await self._type(action)
            elif action_type == "scroll":
                return await self._scroll(action)
            elif action_type == "wait":
                return await self._wait(action)
            elif action_type == "navigate":
                return await self._navigate(action)
            elif action_type == "select":
                return await self._select(action)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action_type}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Action failed: {str(e)}"
            }

    async def _click(self, action: dict) -> dict:
        """Click an element by its indexed ID."""
        element_id = action.get("element_id")
        if element_id is None:
            return {"status": "error", "message": "Missing element_id for click"}

        elem = self.indexer.get_by_id(element_id)
        if not elem:
            return {"status": "error", "message": f"Element {element_id} not found"}

        page = await self.controller.get_page()
        url_before = self.controller.current_url()

        # Try clicking by selector, fall back to coordinates
        try:
            locator = page.locator(elem.css_selector).first
            await locator.click(timeout=5000)
        except Exception:
            # Fallback: click by coordinates
            if elem.rect:
                x = elem.rect.get("x", 0) + elem.rect.get("width", 0) // 2
                y = elem.rect.get("y", 0) + elem.rect.get("height", 0) // 2
                await page.mouse.click(x, y)
            else:
                return {"status": "error", "message": f"Cannot locate element {element_id}"}

        # Wait for potential navigation or DOM change
        await self.controller.wait_for_stable_dom(timeout=3000)

        url_after = self.controller.current_url()
        navigated = url_before != url_after

        return {
            "status": "success",
            "message": f"Clicked [{element_id}] \"{elem.display_text}\""
                       + (f" → navigated to {url_after}" if navigated else ""),
            "url": url_after,
            "navigated": navigated,
        }

    async def _type(self, action: dict) -> dict:
        """Type text into an element by its indexed ID."""
        element_id = action.get("element_id")
        text = action.get("text", "")

        if element_id is None:
            return {"status": "error", "message": "Missing element_id for type"}

        elem = self.indexer.get_by_id(element_id)
        if not elem:
            return {"status": "error", "message": f"Element {element_id} not found"}

        # Credential token substitution
        text = self._substitute_credentials(text)

        page = await self.controller.get_page()

        try:
            locator = page.locator(elem.css_selector).first
            # Clear existing content first
            await locator.click(timeout=3000)
            await locator.fill(text, timeout=5000)
        except Exception:
            # Fallback: click coordinates then type
            if elem.rect:
                x = elem.rect.get("x", 0) + elem.rect.get("width", 0) // 2
                y = elem.rect.get("y", 0) + elem.rect.get("height", 0) // 2
                await page.mouse.click(x, y)
                # Select all and replace
                await page.keyboard.press("Control+a")
                await page.keyboard.type(text, delay=30)
            else:
                return {"status": "error", "message": f"Cannot locate element {element_id}"}

        # Mask credential values in the result message
        display_text = text
        if "__CREDENTIAL_" in action.get("text", ""):
            display_text = "****"

        return {
            "status": "success",
            "message": f"Typed \"{display_text}\" into [{element_id}] \"{elem.display_text}\"",
            "url": self.controller.current_url(),
        }

    async def _scroll(self, action: dict) -> dict:
        """Scroll the page up or down."""
        direction = action.get("direction", "down").lower()
        amount = action.get("amount", 500)

        page = await self.controller.get_page()

        if direction == "down":
            await page.mouse.wheel(0, amount)
        elif direction == "up":
            await page.mouse.wheel(0, -amount)
        else:
            return {"status": "error", "message": f"Invalid scroll direction: {direction}"}

        await page.wait_for_timeout(500)

        return {
            "status": "success",
            "message": f"Scrolled {direction} by {amount}px",
            "url": self.controller.current_url(),
        }

    async def _wait(self, action: dict) -> dict:
        """Wait for a specified number of seconds."""
        seconds = action.get("seconds", 2)
        seconds = min(seconds, 10)  # cap at 10s

        page = await self.controller.get_page()
        await page.wait_for_timeout(int(seconds * 1000))

        return {
            "status": "success",
            "message": f"Waited {seconds} seconds",
            "url": self.controller.current_url(),
        }

    async def _navigate(self, action: dict) -> dict:
        """Navigate to a URL."""
        url = action.get("url", "")
        if not url:
            return {"status": "error", "message": "Missing URL for navigate"}

        await self.controller.navigate(url)

        return {
            "status": "success",
            "message": f"Navigated to {self.controller.current_url()}",
            "url": self.controller.current_url(),
        }

    async def _select(self, action: dict) -> dict:
        """Select an option from a dropdown."""
        element_id = action.get("element_id")
        value = action.get("value", "")

        if element_id is None:
            return {"status": "error", "message": "Missing element_id for select"}

        elem = self.indexer.get_by_id(element_id)
        if not elem:
            return {"status": "error", "message": f"Element {element_id} not found"}

        page = await self.controller.get_page()
        locator = page.locator(elem.css_selector).first
        await locator.select_option(value, timeout=5000)

        return {
            "status": "success",
            "message": f"Selected \"{value}\" in [{element_id}]",
            "url": self.controller.current_url(),
        }

    def _substitute_credentials(self, text: str) -> str:
        """Replace credential tokens with actual values."""
        if "__CREDENTIAL_EMAIL__" in text:
            text = text.replace("__CREDENTIAL_EMAIL__", self.credentials.get("email", ""))
        if "__CREDENTIAL_PASSWORD__" in text:
            text = text.replace("__CREDENTIAL_PASSWORD__", self.credentials.get("password", ""))
        if "__CREDENTIAL_USERNAME__" in text:
            text = text.replace("__CREDENTIAL_USERNAME__", self.credentials.get("username", ""))
        return text
