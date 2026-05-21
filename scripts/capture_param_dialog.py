"""Capture SAP Query Manager parameter dialog HTML and screenshot.

Runs the query `llamadas_correctivas_serial` which contains a `[%0]` parameter,
clicks Execute, waits for the parameter dialog to appear, and captures both
a screenshot and the full page HTML for analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import get_settings
from infrastructure.sap.playwright_client import PlaywrightClient
from infrastructure.sap.sap_session_manager import SapSessionManager

# Selectors we will try for the query textarea and execute button
QUERY_TEXTAREA_FALLBACKS: tuple[str, ...] = (
    "textarea#query",
    "textarea[name='query']",
    "textarea",
)

EXECUTE_BUTTON_FALLBACKS: tuple[str, ...] = (
    "#btnExecute",
    "input#btnExecute",
    "input[type='button'][title='Run script']",
    "button:has-text('Execute')",
    "input[type='button'][value='Execute']",
    "input[type='submit'][value='Execute']",
)


def _selector_exists(page, selector: str) -> bool:
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False


def _fill_first_available(page, selectors: tuple[str, ...], value: str, context: str) -> str:
    for selector in selectors:
        if _selector_exists(page, selector):
            page.fill(selector, value)
            return selector
    raise RuntimeError(f"{context} not found")


def _click_first_available(page, selectors: tuple[str, ...], context: str) -> str:
    for selector in selectors:
        if _selector_exists(page, selector):
            page.click(selector)
            return selector
    raise RuntimeError(f"{context} not found")


def main() -> int:
    settings = get_settings()

    # Dedicated output directory for the parameter dialog capture
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact_dir = Path(settings.sap_debug_artifacts_path) / f"param_dialog_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = (artifact_dir / "dialog.png").resolve()
    html_path = (artifact_dir / "dialog.html").resolve()
    pre_dialog_screenshot = (artifact_dir / "pre_dialog.png").resolve()
    pre_dialog_html = (artifact_dir / "pre_dialog.html").resolve()

    manager = SapSessionManager(
        base_url=settings.sap_base_url,
        debug_capture=False,
        debug_artifacts_path=settings.sap_debug_artifacts_path,
        headless=False,  # Non-headless so we can see what happens if it fails
    )

    # Load the SQL that contains [%0]
    sql_path = Path("queries/sql/llamadas_correctivas_serial.sql")
    sql_text = sql_path.read_text(encoding="utf-8")

    with PlaywrightClient(headless=False) as browser:
        page = browser.new_page()

        # 1. Login
        print("[1/5] Logging in to SAP...")
        manager.login(
            page=page,
            username=settings.sap_username,
            password=settings.sap_password,
            company_db=settings.sap_company_db,
            correlation_id="param_dialog_capture",
        )
        print("  -> Login OK")

        # 2. Navigate to Query Manager
        print("[2/5] Opening Query Manager...")
        manager.open_query_manager(page=page, correlation_id="param_dialog_capture")
        print("  -> Query Manager OK")

        # 3. Fill the SQL textarea
        print("[3/5] Filling query SQL...")
        textarea_sel = _fill_first_available(page, QUERY_TEXTAREA_FALLBACKS, sql_text, "Query textarea")
        print(f"  -> Filled using selector: {textarea_sel}")

        # Capture state BEFORE clicking Execute
        pre_dialog_screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(pre_dialog_screenshot), full_page=True)
        pre_dialog_html.write_text(page.content(), encoding="utf-8")
        print(f"  -> Pre-dialog artifacts saved: {pre_dialog_screenshot}, {pre_dialog_html}")

        # 4. Click Execute
        print("[4/5] Clicking Execute...")
        exec_sel = _click_first_available(page, EXECUTE_BUTTON_FALLBACKS, "Execute button")
        print(f"  -> Clicked using selector: {exec_sel}")

        # 5. Wait for dialog and capture
        print("[5/5] Waiting for parameter dialog (up to 10s)...")
        dialog_detected = False

        # Try multiple strategies to detect the dialog
        # Strategy A: wait for any dialog-like element
        dialog_selectors = [
            "div[role='dialog']",
            "div.dialog",
            "div.Dialog",
            "div[class*='dialog']",
            "div[class*='Dialog']",
            "div[class*='prompt']",
            "div[class*='Prompt']",
            "table[class*='dialog']",
            "#dialog",
            "#Dialog",
            "iframe",  # Some SAP dialogs are in iframes
        ]

        for sel in dialog_selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                print(f"  -> Dialog detected via selector: {sel}")
                dialog_detected = True
                break
            except Exception:
                continue

        # Strategy B: if no dialog selector matched, wait for URL change or new page
        if not dialog_detected:
            try:
                page.wait_for_timeout(5000)
                print("  -> Waited 5s, checking page state...")
                # Check if there are any input fields that weren't there before
                inputs = page.locator("input[type='text'], input:not([type]), textarea").all()
                print(f"  -> Found {len(inputs)} input-like elements on page")
                dialog_detected = True  # We'll analyze the HTML regardless
            except Exception:
                pass

        # Capture the dialog state
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        print(f"  -> Dialog artifacts saved: {screenshot_path}, {html_path}")

        # Also try to capture iframes separately
        frames = page.frames
        if len(frames) > 1:
            print(f"  -> Page has {len(frames)} frames, capturing each...")
            for i, frame in enumerate(frames):
                frame_html_path = artifact_dir / f"frame_{i}.html"
                try:
                    frame_html_path.write_text(frame.content(), encoding="utf-8")
                    print(f"     -> Frame {i}: {frame_html_path}")
                except Exception as e:
                    print(f"     -> Frame {i}: could not capture ({e})")

    print(f"\n=== CAPTURE COMPLETE ===")
    print(f"Directory: {artifact_dir.resolve()}")
    print(f"Pre-dialog screenshot: {pre_dialog_screenshot}")
    print(f"Pre-dialog HTML: {pre_dialog_html}")
    print(f"Dialog screenshot: {screenshot_path}")
    print(f"Dialog HTML: {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
