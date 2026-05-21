from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config.settings import Settings
from domain.errors import SapConnectionError, SapQueryExecutionError
from infrastructure.sap.query_executor import SapQueryExecutor


class _FakeContext:
    def __init__(self, closed: bool = False) -> None:
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


class _FakePage:
    def __init__(self, *, page_closed: bool = False, context_closed: bool = False) -> None:
        self._page_closed = page_closed
        self.context = _FakeContext(closed=context_closed)

    def is_closed(self) -> bool:
        return self._page_closed


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def __enter__(self) -> _FakeBrowser:
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None

    def new_page(self) -> _FakePage:
        return self._page


def _base_settings() -> Settings:
    return Settings(sap_mock_mode=False, sap_debug_capture=True)


def test_preserves_existing_diagnostics_without_secondary_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _base_settings()
    executor = SapQueryExecutor(settings)

    page = _FakePage(page_closed=True, context_closed=True)
    monkeypatch.setattr("infrastructure.sap.query_executor.PlaywrightClient", lambda **_kwargs: _FakeBrowser(page))

    existing_msg = (
        "Could not authenticate in SAP. Debug artifacts saved: "
        "screenshot=artifacts/live_debug/a.png, html=artifacts/live_debug/a.html."
    )
    monkeypatch.setattr(executor.session, "login", lambda *_args, **_kwargs: (_ for _ in ()).throw(SapConnectionError(existing_msg)))

    with pytest.raises(SapQueryExecutionError) as err:
        executor.run_query.__wrapped__(executor, "sales_by_customer", "SELECT 1", "cid-1")

    message = str(err.value)
    assert existing_msg in message
    assert "debug_capture_failed" not in message


def test_adds_capture_detail_when_missing_and_page_available(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _base_settings()
    executor = SapQueryExecutor(settings)

    page = _FakePage(page_closed=False, context_closed=False)
    monkeypatch.setattr("infrastructure.sap.query_executor.PlaywrightClient", lambda **_kwargs: _FakeBrowser(page))
    monkeypatch.setattr(
        executor.session,
        "login",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SapConnectionError("Could not authenticate in SAP.")),
    )

    class _Artifacts:
        screenshot_path = "artifacts/live_debug/cid-2/page.png"
        html_path = "artifacts/live_debug/cid-2/page.html"

    monkeypatch.setattr("infrastructure.sap.query_executor.build_artifact_paths", lambda *_args, **_kwargs: _Artifacts())
    monkeypatch.setattr("infrastructure.sap.query_executor.capture_page_artifacts", lambda *_args, **_kwargs: None)

    with pytest.raises(SapQueryExecutionError) as err:
        executor.run_query.__wrapped__(executor, "sales_by_customer", "SELECT 1", "cid-2")

    message = str(err.value)
    assert "Could not authenticate in SAP." in message
    assert "debug_artifacts=screenshot:artifacts/live_debug/cid-2/page.png,html:artifacts/live_debug/cid-2/page.html" in message
    assert "debug_capture_failed" not in message


class _FakeLocator:
    """Minimal fake for Playwright locator that returns preset text."""
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text_content(self) -> str:
        return self._text


class _FakePageWithInfo:
    """Fake page that supports locator() for _read_info_messages."""

    def __init__(self, info_text: str = "") -> None:
        self._info_text = info_text
        self._page_closed = False
        self.context = _FakeContext(closed=False)

    def is_closed(self) -> bool:
        return self._page_closed

    def locator(self, selector: str) -> _FakeLocator:
        assert selector == "#infoMessages"
        return _FakeLocator(self._info_text)


class TestReadInfoMessages:
    """Test _read_info_messages reads from #infoMessages."""

    def test_returns_text_content(self) -> None:
        page = _FakePageWithInfo(info_text="Query completed.")
        executor = SapQueryExecutor(_base_settings())
        result = executor._read_info_messages(page)
        assert result == "Query completed."

    def test_returns_empty_on_missing_text(self) -> None:
        page = _FakePageWithInfo(info_text="")
        executor = SapQueryExecutor(_base_settings())
        result = executor._read_info_messages(page)
        assert result == ""

    def test_returns_empty_on_exception(self) -> None:
        class _BrokenPage:
            def locator(self, selector: str) -> None:
                raise RuntimeError("page closed")
        executor = SapQueryExecutor(_base_settings())
        result = executor._read_info_messages(_BrokenPage())
        assert result == ""


class TestCaptureEmptyResult:
    """Test _capture_empty_result saves diagnostics when appropriate."""

    def test_captures_when_debug_enabled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        settings = Settings(sap_mock_mode=False, sap_debug_capture=True, sap_debug_artifacts_path=str(tmp_path))
        executor = SapQueryExecutor(settings)
        page = _FakePage(page_closed=False, context_closed=False)

        captured_paths = []
        monkeypatch.setattr(
            "infrastructure.sap.query_executor.capture_page_artifacts",
            lambda page_obj, paths: captured_paths.append(paths),
        )

        executor._capture_empty_result(page, "test_query", "cid-1", reason="empty", info_msg="Query completed.")
        assert len(captured_paths) == 1

    def test_skips_when_debug_disabled(self) -> None:
        settings = Settings(sap_mock_mode=False, sap_debug_capture=False)
        executor = SapQueryExecutor(settings)
        page = _FakePage(page_closed=False, context_closed=False)

        # Should not raise or capture — just return silently
        executor._capture_empty_result(page, "test_query", "cid-1", reason="empty", info_msg="")

    def test_skips_when_error_in_info_msg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = Settings(sap_mock_mode=False, sap_debug_capture=True)
        executor = SapQueryExecutor(settings)
        page = _FakePage(page_closed=False, context_closed=False)

        captured = []
        monkeypatch.setattr(
            "infrastructure.sap.query_executor.capture_page_artifacts",
            lambda *_a, **_k: captured.append(True),
        )

        # "Error" in info_msg should skip capture (it's handled by exception path)
        executor._capture_empty_result(page, "q", "cid", reason="timeout", info_msg="Error: timeout")
        assert len(captured) == 0

    def test_skips_when_page_closed(self) -> None:
        settings = Settings(sap_mock_mode=False, sap_debug_capture=True)
        executor = SapQueryExecutor(settings)
        page = _FakePage(page_closed=True, context_closed=False)

        # Should not raise — just silently skip
        executor._capture_empty_result(page, "test_query", "cid-1", reason="empty", info_msg="")
