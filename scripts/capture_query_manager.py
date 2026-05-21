"""One-off diagnostic capture for SAP Query Manager page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import get_settings
from domain.errors import SapConnectionError, SapSelectorError
from infrastructure.sap.playwright_client import PlaywrightClient
from infrastructure.sap.sap_session_manager import SapSessionManager


def _capture_dir(base_path: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(base_path) / f"manual_capture_{stamp}"


def main() -> int:
    settings = get_settings()
    artifact_dir = _capture_dir(settings.sap_debug_artifacts_path)
    screenshot_path = (artifact_dir / "page.png").resolve()
    html_path = (artifact_dir / "page.html").resolve()

    manager = SapSessionManager(
        base_url=settings.sap_base_url,
        debug_capture=False,
        debug_artifacts_path=settings.sap_debug_artifacts_path,
        headless=settings.sap_headless,
    )

    login_ok = False
    query_manager_ok = False
    error_message = ""

    with PlaywrightClient(headless=settings.sap_headless) as browser:
        page = browser.new_page()
        try:
            manager.login(
                page=page,
                username=settings.sap_username,
                password=settings.sap_password,
                company_db=settings.sap_company_db,
                correlation_id="manual_capture",
            )
            login_ok = True

            try:
                manager.open_query_manager(page=page, correlation_id="manual_capture")
                query_manager_ok = True
            except SapSelectorError as exc:
                error_message = str(exc)

            artifact_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(page.content(), encoding="utf-8")
        except SapConnectionError as exc:
            error_message = str(exc)

    capture_ok = login_ok and screenshot_path.exists() and html_path.exists()

    print(f"screenshot_path={screenshot_path}")
    print(f"html_path={html_path}")
    print(f"login_ok={login_ok}")
    print(f"query_manager_ok={query_manager_ok}")
    print(f"capture_ok={capture_ok}")
    if error_message:
        print(f"error={error_message}")

    return 0 if capture_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
