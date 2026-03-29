"""
Browser Tool — wraps the existing browser agent infrastructure as a unified tool.

Uses a persistent background event loop so Playwright's browser stays alive
across multiple step executions (Playwright REQUIRES a persistent event loop —
you can't asyncio.run() each step separately because that kills the loop + browser).

KEY ACTIONS:
  - inspect: See actual page elements before acting (the perception layer)
  - wait_for: Wait for a specific selector to appear
  - press_key: Send keyboard keys (Enter, Tab, ArrowDown, Escape, etc.)
  - try_click: Click optional elements without failing
"""

import asyncio
import threading
from typing import Optional
from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState


class BrowserTool(BaseTool):
    name = "browser"
    description = (
        "Control a real web browser for web tasks. "
        "ALWAYS use 'inspect' FIRST after opening a page to see actual elements and selectors. "
        "Use 'wait_for' to wait for elements. Use 'press_key' for keyboard actions (Enter, Tab, ArrowDown). "
        "Use 'try_click' for optional elements. Use 'close_browser' only when browser is no longer needed."
    )
    actions = [
        "open_url", "inspect", "click", "try_click", "type_text", "press_key",
        "select_option", "wait_for", "scroll", "navigate",
        "extract_text", "screenshot", "wait", "close_browser",
    ]

    def __init__(self, api_key: str = "", headless: bool = False):
        self._api_key = api_key
        self._headless = headless
        self._controller = None
        self._initialized = False

        # Persistent event loop running in a background thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_loop()

    def _start_loop(self):
        """Start a persistent background event loop for Playwright."""
        self._loop = asyncio.new_event_loop()

        def _run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._loop_thread = threading.Thread(target=_run_loop, args=(self._loop,), daemon=True)
        self._loop_thread.start()

    def _run_async(self, coro, timeout=60):
        """Submit a coroutine to the persistent loop and wait for result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    async def _ensure_browser(self):
        """Lazy-initialize the browser on first use."""
        if self._initialized:
            return

        try:
            from agents.browser_agent.browser.controller import BrowserController
            self._controller = BrowserController(headless=self._headless)
            await self._controller.launch()
            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to launch browser: {e}")

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        """Execute browser action through the persistent event loop."""
        try:
            return self._run_async(self._execute_async(action, args, state), timeout=60)
        except Exception as e:
            return ToolResult.error(f"Browser tool error: {str(e)}")

    async def _execute_async(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            await self._ensure_browser()

            dispatch = {
                "open_url": self._open_url,
                "inspect": self._inspect,
                "click": self._click,
                "try_click": self._try_click,
                "type_text": self._type_text,
                "press_key": self._press_key,
                "select_option": self._select_option,
                "wait_for": self._wait_for,
                "scroll": self._scroll,
                "navigate": self._navigate,
                "extract_text": self._extract_text,
                "screenshot": self._screenshot,
                "wait": self._wait,
                "close_browser": self._close_browser,
            }

            handler = dispatch.get(action)
            if handler:
                return await handler(args, state)
            return ToolResult.error(f"Unknown browser action: {action}")

        except Exception as e:
            return ToolResult.fail(f"Browser action failed: {str(e)}", retryable=True)

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        valid, err = super().validate(action, args)
        if not valid:
            return valid, err

        if action in ("open_url", "navigate") and "url" not in args:
            return False, "Missing required arg: 'url'"
        if action == "click" and "selector" not in args and "element_id" not in args:
            return False, "Missing required arg: 'selector' or 'element_id'"
        if action == "type_text" and "text" not in args:
            return False, "Missing required arg: 'text'"
        if action == "press_key" and "key" not in args:
            return False, "Missing required arg: 'key'"
        if action == "wait_for" and "selector" not in args:
            return False, "Missing required arg: 'selector'"

        return True, ""

    # ─── PERCEPTION ──────────────────────────────────────────────

    async def _inspect(self, args: dict, state: ExecutionState) -> ToolResult:
        """
        THE PERCEPTION LAYER — scan the page and return all visible interactive elements.
        Returns real selectors the planner can use in subsequent steps.
        
        Args:
            scope (str): CSS selector to limit inspection scope (default: "body")
            limit (int): Max elements to return (default: 40)
        """
        page = await self._controller.get_page()
        scope = args.get("scope", "body")
        limit = args.get("limit", 40)

        js_code = """
        (args) => {
            const scope = document.querySelector(args.scope) || document.body;
            const limit = args.limit;
            const elements = [];
            
            // Interactive element selectors
            const interactiveSelectors = 'a, button, input, textarea, select, [role="button"], [role="link"], [role="menuitem"], [role="option"], [role="tab"], [onclick], [contenteditable], label, li[class*="item"], li[class*="option"], li[class*="suggestion"], span[class*="item"], div[class*="item"], div[role="listbox"] *, ul[role="listbox"] *';
            
            const found = scope.querySelectorAll(interactiveSelectors);
            
            for (let i = 0; i < found.length && elements.length < limit; i++) {
                const el = found[i];
                
                // Skip hidden elements
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                
                // Build the best selector for this element
                let selector = '';
                if (el.id) {
                    selector = '#' + CSS.escape(el.id);
                } else if (el.getAttribute('name')) {
                    selector = el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]';
                } else if (el.getAttribute('data-testid')) {
                    selector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
                } else if (el.getAttribute('aria-label')) {
                    selector = '[aria-label="' + el.getAttribute('aria-label') + '"]';
                } else if (el.getAttribute('placeholder')) {
                    selector = '[placeholder="' + el.getAttribute('placeholder') + '"]';
                } else if (el.className && typeof el.className === 'string' && el.className.trim()) {
                    const classes = el.className.trim().split(/\\s+/).filter(c => c.length < 40).slice(0, 2);
                    if (classes.length > 0) {
                        selector = el.tagName.toLowerCase() + '.' + classes.join('.');
                    }
                }
                
                if (!selector) {
                    // Generate nth-child selector as fallback
                    const parent = el.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children);
                        const index = siblings.indexOf(el) + 1;
                        const parentSelector = parent.id ? '#' + CSS.escape(parent.id) : parent.tagName.toLowerCase();
                        selector = parentSelector + ' > ' + el.tagName.toLowerCase() + ':nth-child(' + index + ')';
                    } else {
                        selector = el.tagName.toLowerCase();
                    }
                }
                
                // Get element info
                const tag = el.tagName.toLowerCase();
                const type = el.getAttribute('type') || '';
                const text = (el.innerText || el.textContent || '').trim().substring(0, 60);
                const value = el.value || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                
                elements.push({
                    tag: tag,
                    type: type,
                    selector: selector,
                    text: text || placeholder || ariaLabel || value || tag,
                    placeholder: placeholder,
                    value: value.substring(0, 30),
                    visible: true,
                });
            }
            
            return elements;
        }
        """.strip()

        try:
            elements = await page.evaluate(js_code, {"scope": scope, "limit": limit})

            # Format as readable list for LLM
            lines = []
            for i, el in enumerate(elements):
                tag_info = el['tag']
                if el['type']:
                    tag_info += f"[{el['type']}]"
                text_preview = el['text'][:50] if el['text'] else ""
                
                line = f"  [{i}] <{tag_info}> selector=\"{el['selector']}\""
                if text_preview:
                    line += f" text=\"{text_preview}\""
                if el['placeholder']:
                    line += f" placeholder=\"{el['placeholder']}\""
                if el['value']:
                    line += f" value=\"{el['value']}\""
                lines.append(line)

            summary = "\n".join(lines) if lines else "  (no interactive elements found)"
            result_text = f"Found {len(elements)} interactive elements:\n{summary}"

            return ToolResult.success(
                result=result_text,
                message=f"Inspected page: {len(elements)} interactive elements found",
                state_update={"custom.page_elements": result_text},
            )
        except Exception as e:
            return ToolResult.fail(f"Inspect failed: {str(e)}", retryable=True)

    async def _wait_for(self, args: dict, state: ExecutionState) -> ToolResult:
        """Wait for a specific CSS selector to appear on the page."""
        page = await self._controller.get_page()
        selector = args["selector"]
        timeout = args.get("timeout", 10000)

        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            return ToolResult.success(
                message=f"Element appeared: {selector}",
                state_update={"custom.waited_for": selector},
            )
        except Exception:
            return ToolResult.fail(
                f"Element not found within {timeout}ms: {selector}", retryable=True
            )

    # ─── INTERACTION ACTIONS ─────────────────────────────────────

    async def _open_url(self, args: dict, state: ExecutionState) -> ToolResult:
        url = args["url"]
        await self._controller.navigate(url)
        current_url = self._controller.current_url()
        title = await self._controller.current_title()

        return ToolResult.success(
            result={"url": current_url, "title": title},
            message=f"Opened: {title} ({current_url})",
            state_update={"current_url": current_url, "custom.page_title": title},
        )

    async def _click(self, args: dict, state: ExecutionState) -> ToolResult:
        page = await self._controller.get_page()
        selector = args.get("selector", "")
        element_id = args.get("element_id")

        if element_id is not None:
            selector = f"[data-agent-id='{element_id}']"

        try:
            await page.click(selector, timeout=10000)
            current_url = self._controller.current_url()
            return ToolResult.success(
                message=f"Clicked: {selector}",
                state_update={"current_url": current_url},
            )
        except Exception as e:
            return ToolResult.fail(f"Click failed on '{selector}': {str(e)}", retryable=True)

    async def _try_click(self, args: dict, state: ExecutionState) -> ToolResult:
        """Non-failing click — returns success even if element not found."""
        page = await self._controller.get_page()
        selector = args.get("selector", "")
        timeout = args.get("timeout", 3000)

        try:
            await page.click(selector, timeout=timeout)
            return ToolResult.success(message=f"Clicked optional element: {selector}")
        except Exception:
            return ToolResult.success(
                message=f"Optional element not found (OK): {selector}",
                state_update={"custom.skipped_optional": selector},
            )

    async def _type_text(self, args: dict, state: ExecutionState) -> ToolResult:
        page = await self._controller.get_page()
        text = args["text"]
        selector = args.get("selector", "")
        element_id = args.get("element_id")
        clear_first = args.get("clear", False)

        if element_id is not None:
            selector = f"[data-agent-id='{element_id}']"

        try:
            if selector:
                if clear_first:
                    await page.fill(selector, "", timeout=10000)
                # Try fill first, fall back to click+type for non-standard inputs
                try:
                    await page.fill(selector, text, timeout=5000)
                except Exception:
                    await page.click(selector, timeout=5000)
                    await page.keyboard.type(text, delay=50)
            else:
                await page.keyboard.type(text, delay=50)

            preview = text[:50] + ("..." if len(text) > 50 else "")
            return ToolResult.success(message=f"Typed: '{preview}'")
        except Exception as e:
            return ToolResult.fail(f"Type failed: {str(e)}", retryable=True)

    async def _press_key(self, args: dict, state: ExecutionState) -> ToolResult:
        """
        Press keyboard keys — essential for autocompletes, form navigation, etc.
        
        Args:
            key: Key to press (Enter, Tab, ArrowDown, ArrowUp, Escape, Backspace, etc.)
            count: Number of times to press (default 1)
            selector: Optional — focus this element first before pressing
        """
        page = await self._controller.get_page()
        key = args["key"]
        count = args.get("count", 1)
        selector = args.get("selector", "")

        try:
            if selector:
                await page.click(selector, timeout=5000)
            
            for _ in range(count):
                await page.keyboard.press(key)
                await asyncio.sleep(0.1)

            return ToolResult.success(message=f"Pressed '{key}' x{count}")
        except Exception as e:
            return ToolResult.fail(f"Key press failed: {str(e)}", retryable=True)

    async def _select_option(self, args: dict, state: ExecutionState) -> ToolResult:
        """Select from a dropdown/autocomplete by typing + waiting + clicking result."""
        page = await self._controller.get_page()
        selector = args.get("selector", "")
        text = args.get("text", "")
        result_selector = args.get("result_selector", "")

        try:
            # Click the input to focus
            if selector:
                await page.click(selector, timeout=5000)
                await asyncio.sleep(0.3)

            # Type the search text
            await page.keyboard.type(text, delay=80)
            await asyncio.sleep(1.5)  # Wait for autocomplete suggestions

            # Click the first result if a result selector is provided
            if result_selector:
                try:
                    await page.click(result_selector, timeout=5000)
                except Exception:
                    # Fallback: press ArrowDown + Enter
                    await page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.2)
                    await page.keyboard.press("Enter")
            else:
                # Default: ArrowDown + Enter to select first suggestion
                await page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.2)
                await page.keyboard.press("Enter")

            await asyncio.sleep(0.5)
            return ToolResult.success(message=f"Selected option for: '{text}'")
        except Exception as e:
            return ToolResult.fail(f"Select option failed: {str(e)}", retryable=True)

    # ─── NAVIGATION & DATA ───────────────────────────────────────

    async def _scroll(self, args: dict, state: ExecutionState) -> ToolResult:
        page = await self._controller.get_page()
        direction = args.get("direction", "down")
        amount = args.get("amount", 300)

        delta = amount if direction == "down" else -amount
        await page.mouse.wheel(0, delta)

        return ToolResult.success(message=f"Scrolled {direction} by {amount}px")

    async def _navigate(self, args: dict, state: ExecutionState) -> ToolResult:
        return await self._open_url(args, state)

    async def _extract_text(self, args: dict, state: ExecutionState) -> ToolResult:
        page = await self._controller.get_page()
        selector = args.get("selector", "body")

        try:
            text = await page.inner_text(selector, timeout=10000)
            if len(text) > 5000:
                text = text[:5000] + "\n... [text truncated]"
            return ToolResult.success(
                result=text,
                message=f"Extracted {len(text)} chars",
                state_update={"last_output": text[:500]},
            )
        except Exception as e:
            return ToolResult.fail(f"Extract failed: {str(e)}", retryable=True)

    async def _screenshot(self, args: dict, state: ExecutionState) -> ToolResult:
        page = await self._controller.get_page()
        path = args.get("path", "/tmp/screenshot.png")

        try:
            await page.screenshot(path=path, full_page=args.get("full_page", False))
            return ToolResult.success(
                result=path,
                message=f"Screenshot saved to {path}",
            )
        except Exception as e:
            return ToolResult.fail(f"Screenshot failed: {str(e)}")

    async def _wait(self, args: dict, state: ExecutionState) -> ToolResult:
        seconds = args.get("seconds", 2)
        await asyncio.sleep(seconds)
        return ToolResult.success(message=f"Waited {seconds}s")

    async def _close_browser(self, args: dict, state: ExecutionState) -> ToolResult:
        """Explicitly close the browser. Only use when browser is no longer needed."""
        try:
            if self._controller:
                await self._controller.close()
                self._initialized = False
                self._controller = None
            return ToolResult.success(message="Browser closed")
        except Exception as e:
            return ToolResult.fail(f"Failed to close browser: {str(e)}")

    # ─── Cleanup ────────────────────────────────────────────────

    def close(self):
        """Synchronous cleanup — shuts down browser and event loop."""
        if self._controller and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._controller.close(), self._loop
                )
                future.result(timeout=10)
            except Exception:
                pass

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=5)
            self._loop = None
            self._loop_thread = None

        self._initialized = False
