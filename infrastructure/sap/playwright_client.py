"""Playwright async browser client wrapper."""
from playwright.async_api import Browser, Page, async_playwright


class PlaywrightClient:
    """Manages browser lifecycle for SAP automation (async)."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "PlaywrightClient":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self._browser:
            raise RuntimeError("Browser is not initialized")
        return await self._browser.new_page()
