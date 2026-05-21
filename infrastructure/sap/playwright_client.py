"""Playwright browser client wrapper."""

from playwright.sync_api import Browser, Page, sync_playwright


class PlaywrightClient:
    """Manages browser lifecycle for SAP automation."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    def __enter__(self) -> "PlaywrightClient":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def new_page(self) -> Page:
        if not self._browser:
            raise RuntimeError("Browser is not initialized")
        return self._browser.new_page()
