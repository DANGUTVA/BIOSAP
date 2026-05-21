from __future__ import annotations

import pytest

from domain.errors import SapSelectorError
from infrastructure.sap.sap_session_manager import SapSessionManager


class FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakePage:
    def __init__(self, available_selectors: set[str] | None = None) -> None:
        self.available_selectors = available_selectors or set()
        self.fills: list[tuple[str, str]] = []
        self.clicks: list[str] = []

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(1 if selector in self.available_selectors else 0)

    def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    def click(self, selector: str) -> None:
        self.clicks.append(selector)

    def goto(self, _url: str) -> None:
        return

    def wait_for_load_state(self, _state: str) -> None:
        return


def test_fill_company_db_skips_blank_value() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(available_selectors={manager.selectors.company_db})

    filled = manager._fill_company_db_if_available(page, "")

    assert filled is False
    assert page.fills == []


def test_fill_company_db_skips_when_selector_missing() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(available_selectors=set())

    filled = manager._fill_company_db_if_available(page, "SBODEMO")

    assert filled is False
    assert page.fills == []


def test_fill_company_db_when_value_and_selector_exist() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(available_selectors={manager.selectors.company_db})

    filled = manager._fill_company_db_if_available(page, "SBODEMO")

    assert filled is True
    assert page.fills == [(manager.selectors.company_db, "SBODEMO")]


def test_click_first_available_uses_fallback_selector() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(available_selectors={"button:has-text('Login')"})

    used = manager._click_first_available(
        page,
        (manager.selectors.login_button, "button:has-text('Login')"),
        "Login button",
    )

    assert used == "button:has-text('Login')"
    assert page.clicks == ["button:has-text('Login')"]


def test_click_first_available_raises_after_all_options_fail() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(available_selectors=set())

    with pytest.raises(SapSelectorError, match="Login button failed"):
        manager._click_first_available(
            page,
            (manager.selectors.login_button, "button:has-text('Login')"),
            "Login button",
        )


def test_login_continues_when_company_db_selector_missing() -> None:
    manager = SapSessionManager(base_url="https://sap.example.com")
    page = FakePage(
        available_selectors={
            manager.selectors.username,
            manager.selectors.password,
            "button:has-text('Login')",
        }
    )

    manager.login(page, username="user", password="pass", company_db="SBODEMO")

    assert (manager.selectors.company_db, "SBODEMO") not in page.fills
    assert page.clicks == ["button:has-text('Login')"]
