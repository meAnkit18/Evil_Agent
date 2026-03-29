"""
Playwright browser controller.
Manages browser lifecycle, navigation, and page access.
Uses async API for FastAPI compatibility.
"""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class BrowserController:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def launch(self):
        """Launch Chromium browser in visible mode."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        print("🌐 Browser launched")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigate to URL and wait for page load."""
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        # Auto-prepend https:// if no scheme provided
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            await self._page.goto(url, wait_until=wait_until, timeout=30000)
            # Extra wait for dynamic content
            await self._page.wait_for_timeout(1000)
            print(f"📍 Navigated to: {self._page.url}")
        except Exception as e:
            print(f"⚠️ Navigation error: {e}")
            raise

    async def get_page(self) -> Page:
        """Return the active page."""
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    def current_url(self) -> str:
        """Get current page URL."""
        if self._page:
            return self._page.url
        return ""

    async def current_title(self) -> str:
        """Get current page title."""
        if self._page:
            return await self._page.title()
        return ""

    async def wait_for_navigation(self, timeout: int = 10000):
        """Wait for a navigation event (URL change or page load)."""
        if self._page:
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=timeout)
            except Exception:
                pass  # timeout is acceptable — page may not navigate

    async def wait_for_stable_dom(self, timeout: int = 3000):
        """Wait until DOM stops changing (for React/SPA apps)."""
        if not self._page:
            return
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass  # timeout is fine — best effort

    async def close(self):
        """Teardown browser and Playwright."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        print("🌐 Browser closed")
