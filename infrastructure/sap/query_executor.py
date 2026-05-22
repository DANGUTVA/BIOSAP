"""SAP query execution adapter with retry and mock fallback (async)."""

from pathlib import Path
import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import Settings
from app.observability.logger import configure_logger
from domain.errors import SapQueryExecutionError
from infrastructure.html_parsers.bs4_parser import Bs4HtmlTableParser
from infrastructure.sap.diagnostics import build_artifact_paths, capture_page_artifacts
from infrastructure.sap.param_resolver import has_parameters, resolve_parameters
from infrastructure.sap.playwright_client import PlaywrightClient
from infrastructure.sap.sap_session_manager import SapSessionManager


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
)


class SapQueryExecutor:
    """SAP gateway implementation used by the RunQuery use case (async)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = configure_logger(settings.log_level)
        self.parser = Bs4HtmlTableParser()
        self.session = SapSessionManager(
            base_url=settings.sap_base_url,
            debug_capture=settings.sap_debug_capture,
            debug_artifacts_path=settings.sap_debug_artifacts_path,
            headless=settings.sap_headless,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(SapQueryExecutionError),
    )
    async def run_query(
        self,
        query_id: str,
        sql_text: str,
        correlation_id: str,
        *,
        param_overrides: dict[int, str] | None = None,
    ) -> pd.DataFrame:
        """Run query in SAP or load fixture when mock mode is enabled."""
        self.logger.info("Running query_id=%s", query_id)

        if self.settings.sap_mock_mode:
            return self._run_mock(query_id)

        # Resolve [%N] parameters before execution.
        # The SAP Queries web interface does NOT show a popup dialog for
        # parameters like the desktop client does — [%N] is sent literally
        # to the database and matches nothing. We replace them upfront.
        # param_overrides take priority over .env / SAP_PARAM_DEFAULT.
        effective_sql = self._resolve_sql_params(query_id, sql_text, param_overrides=param_overrides)

        try:
            async with PlaywrightClient(headless=self.settings.sap_headless) as browser:
                page = await browser.new_page()
                await self.session.login(
                    page,
                    username=self.settings.sap_username,
                    password=self.settings.sap_password,
                    company_db=self.settings.sap_company_db,
                    correlation_id=correlation_id,
                )
                await self.session.open_query_manager(page, correlation_id=correlation_id)
                await self._fill_first_available(page, QUERY_TEXTAREA_FALLBACKS, effective_sql, "Query textarea")
                await self._click_first_available(page, EXECUTE_BUTTON_FALLBACKS, "Execute button")

                # SAP updates results asynchronously. We must wait for the table to appear.
                # SAP queries can take 60-90+ seconds depending on data volume.
                try:
                    await page.wait_for_selector("#result table", timeout=90000)
                except Exception:
                    # Timeout waiting for table: capture state for diagnosis.
                    info_msg = ""
                    try:
                        info_msg = await page.locator("#infoMessages").text_content() or ""
                    except Exception:
                        pass

                    if "error" in info_msg.lower():
                        raise SapQueryExecutionError(f"SAP query error: {info_msg}")

                    # Capture page state even on timeout for diagnosis
                    await self._capture_empty_result(page, query_id, correlation_id, reason="timeout", info_msg=info_msg)

                    self.logger.warning(
                        "Query %s returned no rows after 90s. InfoMessages: '%s'",
                        query_id,
                        info_msg,
                    )
                    return pd.DataFrame()

                html = await page.content()
                df = self.parser.parse(html)

                # Capture diagnostics when we get an empty result (no rows)
                if df.empty:
                    info_msg = await self._read_info_messages(page)
                    await self._capture_empty_result(page, query_id, correlation_id, reason="empty", info_msg=info_msg)
                    self.logger.warning(
                        "Query %s succeeded but returned 0 rows. InfoMessages: '%s'",
                        query_id,
                        info_msg,
                    )

                return df
        except Exception as exc:
            detail = await self._build_debug_detail(exc=exc, correlation_id=correlation_id, page=locals().get("page"))
            base_message = f"SAP query failed for query_id={query_id}: {exc}"
            raise SapQueryExecutionError(f"{base_message}{detail}") from exc

    @staticmethod
    async def _read_info_messages(page: object) -> str:
        """Read SAP infoMessages element content."""
        try:
            return await page.locator("#infoMessages").text_content() or ""
        except Exception:
            return ""

    async def _capture_empty_result(
        self, page: object, query_id: str, correlation_id: str, reason: str, info_msg: str
    ) -> None:
        """Capture page state for diagnosis when query returns no data."""
        if not self.settings.sap_debug_capture or not self._is_page_usable_for_capture(page):
            return
        if "error" in info_msg.lower():
            return  # already captured by exception handler

        artifact_paths = build_artifact_paths(
            self.settings.sap_debug_artifacts_path,
            correlation_id=correlation_id,
            stage=f"empty_{reason}_{query_id}",
        )
        try:
            await capture_page_artifacts(page, artifact_paths)
            self.logger.info(
                "Empty-result diagnostics saved: screenshot=%s, html=%s",
                artifact_paths.screenshot_path,
                artifact_paths.html_path,
            )
        except Exception as exc:
            self.logger.warning("Failed to capture empty-result diagnostics: %s", exc)

    async def _build_debug_detail(self, exc: Exception, correlation_id: str, page: object | None) -> str:
        if self._has_diagnostic_info(exc):
            return ""
        if (
            self.settings.sap_mock_mode
            or not self.settings.sap_debug_capture
            or page is None
            or not self._is_page_usable_for_capture(page)
        ):
            return ""

        artifact_paths = build_artifact_paths(
            self.settings.sap_debug_artifacts_path,
            correlation_id=correlation_id,
            stage="query_execution",
        )
        try:
            await capture_page_artifacts(page, artifact_paths)
            return (
                " debug_artifacts="
                f"screenshot:{artifact_paths.screenshot_path},html:{artifact_paths.html_path}"
            )
        except Exception as capture_exc:
            return f" debug_capture_failed={capture_exc}"

    @staticmethod
    def _has_diagnostic_info(exc: Exception) -> bool:
        message = str(exc)
        return "Debug artifacts saved" in message or "debug_capture_failed" in message

    @staticmethod
    def _is_page_usable_for_capture(page: object) -> bool:
        try:
            is_closed = getattr(page, "is_closed", None)
            if callable(is_closed) and is_closed():
                return False
        except Exception:
            return False

        try:
            context = getattr(page, "context", None)
            if context is not None:
                close_state = getattr(context, "is_closed", None)
                if callable(close_state) and close_state():
                    return False
        except Exception:
            return False

        return True

    def _run_mock(self, query_id: str) -> pd.DataFrame:
        fixture = Path(self.settings.mock_fixtures_path) / f"{query_id}.csv"
        if not fixture.exists():
            fixture = Path(self.settings.mock_fixtures_path) / "default.csv"
        return pd.read_csv(fixture)

    @staticmethod
    def _read_env_var(name: str) -> str:
        """Read env var, falling back to .env file if os.environ doesn't have it.

        Pydantic Settings loads ``.env`` but does NOT export variables to
        ``os.environ``.  This fallback ensures ``SAP_PARAM_*`` variables
        defined in ``.env`` are found regardless.
        """
        import os

        value = os.environ.get(name, "")
        if value:
            return value

        try:
            from dotenv import dotenv_values

            dotenv_path = Path(".env")
            if dotenv_path.exists():
                parsed = dotenv_values(dotenv_path)
                return parsed.get(name, "")
        except Exception:
            pass

        return ""

    def _resolve_sql_params(
        self,
        query_id: str,
        sql_text: str,
        *,
        param_overrides: dict[int, str] | None = None,
    ) -> str:
        """Replace [%N] placeholders in SQL with configured or default values.

        Parameter values are resolved in this order:
        1. **param_overrides** (user input, highest priority)
        2. Query-specific override from ``SAP_PARAM_<query_id>`` env var
           (JSON dict like ``{"0": "TEST_SERIAL"}``).
        3. Global default from ``SAP_PARAM_DEFAULT`` env var.
        4. Hardcoded fallback ``PARAM_<N>`` so the query at least runs.

        Values are read from ``os.environ`` first, then fall back to the
        ``.env`` file because Pydantic Settings does not export env vars to
        the process environment.

        Returns the SQL with all [%N] placeholders replaced.
        """
        if not has_parameters(sql_text):
            return sql_text

        import json

        param_values: dict[int, str] = {}

        # 1. Query-specific params: SAP_PARAM_<query_id> = '{"0": "value"}'
        query_key = f"SAP_PARAM_{query_id.upper()}"
        raw = self._read_env_var(query_key)
        if raw:
            try:
                parsed = json.loads(raw)
                param_values = {int(k): str(v) for k, v in parsed.items()}
                self.logger.info("Using query-specific params for %s: %s", query_id, param_values)
            except (json.JSONDecodeError, ValueError) as exc:
                self.logger.warning("Invalid %s env var, ignoring: %s", query_key, exc)

        # 2. Global default: SAP_PARAM_DEFAULT
        global_default = self._read_env_var("SAP_PARAM_DEFAULT")

        # 3. Build final values: overrides > explicit > global_default > PARAM_<N> fallback
        indices = set(param_values.keys())
        from infrastructure.sap.param_resolver import extract_param_indices
        for idx in extract_param_indices(sql_text):
            if idx not in param_values:
                param_values[idx] = global_default if global_default else f"PARAM_{idx}"

        # 4. Apply user-provided overrides (highest priority)
        if param_overrides:
            for idx, value in param_overrides.items():
                param_values[idx] = str(value)
            self.logger.info(
                "Applied %d param override(s) for query_id=%s: %s",
                len(param_overrides),
                query_id,
                param_overrides,
            )

        resolved, used = resolve_parameters(sql_text, param_values)

        self.logger.info(
            "Resolved %d parameter(s) for query_id=%s: %s",
            len(used),
            query_id,
            used,
        )
        return resolved

    @staticmethod
    async def _fill_first_available(page: object, selectors: tuple[str, ...], value: str, context: str) -> str:
        for selector in selectors:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await page.fill(selector, value)
                return selector
        raise SapQueryExecutionError(f"{context} not found")

    @staticmethod
    async def _click_first_available(page: object, selectors: tuple[str, ...], context: str) -> str:
        for selector in selectors:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await page.click(selector)
                return selector
        raise SapQueryExecutionError(f"{context} not found")
