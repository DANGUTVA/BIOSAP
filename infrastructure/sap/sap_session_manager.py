"""SAP session management and selector strategy placeholders (async)."""

from dataclasses import dataclass
from typing import Sequence
from playwright.async_api import Page
from domain.errors import SapConnectionError, SapSelectorError
from infrastructure.sap.diagnostics import build_artifact_paths, capture_page_artifacts


@dataclass(frozen=True)
class SapSelectorStrategy:
    """Selectors used for robust SAP automation, to be tuned per tenant."""

    username: str = "input[name='UserName']"
    password: str = "input[name='Password']"
    company_db: str = "input[name='CompanyDB']"
    login_button: str = "button:has-text('Log In')"
    query_manager_menu: str = "text=Query Manager"
    result_table: str = "table"


LOGIN_BUTTON_FALLBACKS: tuple[str, ...] = (
    "button:has-text('Log In')",
    "button:has-text('Login')",
    "input[type='submit'][value='Log In']",
    "input[type='submit'][value='Login']",
    "input#cmdOK",
    "input[name='cmdOK']",
    "input[type='submit'][value='Aceptar']",
)

USERNAME_FALLBACKS: tuple[str, ...] = (
    "input[name='UserName']",
    "input#txtUser",
    "input[name='txtUser']",
    "input[placeholder*='usuario']",
)

PASSWORD_FALLBACKS: tuple[str, ...] = (
    "input[name='Password']",
    "input#txtPassword",
    "input[name='txtPassword']",
    "input[type='password']",
)

QUERY_MANAGER_FALLBACKS: tuple[str, ...] = (
    "text=Query Manager",
    "a:has-text('Query Manager')",
    "text=Queries",
)


class SapSessionManager:
    """Handles SAP login and navigation (async)."""

    def __init__(
        self,
        base_url: str,
        selectors: SapSelectorStrategy | None = None,
        *,
        debug_capture: bool = True,
        debug_artifacts_path: str = "artifacts/live_debug",
        headless: bool = True,
    ) -> None:
        self.base_url = base_url
        self.selectors = selectors or SapSelectorStrategy()
        self._debug_capture = debug_capture
        self._debug_artifacts_path = debug_artifacts_path
        self._headless = headless

    async def login(
        self, page: Page, username: str, password: str, company_db: str | None, correlation_id: str = "sap"
    ) -> None:
        try:
            await page.goto(self.base_url)
            await self._fill_first_available(
                page,
                (self.selectors.username, *USERNAME_FALLBACKS),
                username,
                "Username field",
            )
            await self._fill_first_available(
                page,
                (self.selectors.password, *PASSWORD_FALLBACKS),
                password,
                "Password field",
            )
            await self._fill_company_db_if_available(page, company_db)
            await self._click_first_available(
                page,
                (self.selectors.login_button, *LOGIN_BUTTON_FALLBACKS),
                "Login button",
            )
            await page.wait_for_load_state("networkidle")
        except SapSelectorError:
            raise
        except Exception as exc:
            artifact_msg = await self._capture_debug_artifacts(page, correlation_id, stage="login")
            headless_hint = (
                " Hint: try SAP_HEADLESS=false temporarily to troubleshoot selector timing in a visible browser."
                if self._headless
                else ""
            )
            raise SapConnectionError(f"Could not authenticate in SAP.{artifact_msg}{headless_hint}") from exc

    async def open_query_manager(self, page: Page, correlation_id: str = "sap") -> None:
        try:
            if "qrymngr" in page.url.lower():
                return
            await self._click_first_available(
                page,
                (self.selectors.query_manager_menu, *QUERY_MANAGER_FALLBACKS),
                "Query Manager selector",
            )
            await page.wait_for_load_state("networkidle")
        except SapSelectorError:
            raise
        except Exception as exc:
            artifact_msg = await self._capture_debug_artifacts(page, correlation_id, stage="query_manager")
            raise SapSelectorError(f"Query Manager selector failed.{artifact_msg}") from exc

    async def _capture_debug_artifacts(self, page: Page, correlation_id: str, stage: str) -> str:
        if not self._debug_capture:
            return ""
        artifact_paths = build_artifact_paths(
            self._debug_artifacts_path,
            correlation_id=correlation_id,
            stage=stage,
        )
        try:
            await capture_page_artifacts(page, artifact_paths)
        except Exception as exc:
            return f" Debug capture failed ({exc})."
        return (
            " Debug artifacts saved:"
            f" screenshot={artifact_paths.screenshot_path}, html={artifact_paths.html_path}."
        )

    async def _fill_company_db_if_available(self, page: Page, company_db: str | None) -> bool:
        value = (company_db or "").strip()
        if not value:
            return False
        if not await self._selector_exists(page, self.selectors.company_db):
            return False
        await page.fill(self.selectors.company_db, value)
        return True

    async def _click_first_available(self, page: Page, selectors: Sequence[str], context: str) -> str:
        seen: set[str] = set()
        for selector in selectors:
            if selector in seen:
                continue
            seen.add(selector)
            if await self._selector_exists(page, selector):
                await page.click(selector)
                return selector
        raise SapSelectorError(f"{context} failed")

    async def _fill_first_available(self, page: Page, selectors: Sequence[str], value: str, context: str) -> str:
        seen: set[str] = set()
        for selector in selectors:
            if selector in seen:
                continue
            seen.add(selector)
            if await self._selector_exists(page, selector):
                await page.fill(selector, value)
                return selector
        raise SapSelectorError(f"{context} failed")

    async def _selector_exists(self, page: Page, selector: str) -> bool:
        try:
            return await page.locator(selector).count() > 0
        except Exception:
            return False
