"""Tests for SAP query executor _read_env_var and _resolve_sql_params."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config.settings import Settings
from infrastructure.sap.query_executor import SapQueryExecutor


class TestReadEnvVar:
    """Verify _read_env_var reads from os.environ first, then falls back to .env."""

    def test_reads_from_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SAP_TEST_VAR", "from_environ")
        assert SapQueryExecutor._read_env_var("SAP_TEST_VAR") == "from_environ"

    def test_os_environ_takes_priority_over_dotenv(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("SAP_TEST_PRIORITY", "from_environ")
        env_file = tmp_path / ".env"
        env_file.write_text("SAP_TEST_PRIORITY=from_dotenv\n")
        # Patch Path(".env") to point at tmp_path /.env
        with patch.object(Path, "exists", return_value=True):
            with patch("infrastructure.sap.query_executor.Path") as mock_path_cls:
                mock_path_cls.return_value = env_file
                # os.environ takes priority — should return "from_environ"
                assert SapQueryExecutor._read_env_var("SAP_TEST_PRIORITY") == "from_environ"

    def test_falls_back_to_dotenv(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """When os.environ doesn't have the var, read from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text('SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL={"0": "650017"}\n')
        monkeypatch.delenv("SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL", raising=False)

        with patch.object(Path, "exists", return_value=True):
            with patch("infrastructure.sap.query_executor.Path") as mock_path_cls:
                mock_path_cls.return_value = env_file
                result = SapQueryExecutor._read_env_var("SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL")
                assert result == '{"0": "650017"}'

    def test_returns_empty_when_not_found_anywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SAP_PARAM_NONEXISTENT", raising=False)
        with patch.object(Path, "exists", return_value=False):
            assert SapQueryExecutor._read_env_var("SAP_PARAM_NONEXISTENT") == ""


class TestResolveSqlParams:
    """Verify _resolve_sql_params uses query-specific params from .env."""

    def _make_executor(self, tmp_path: Path) -> SapQueryExecutor:
        settings = Settings(sap_mock_mode=True)
        return SapQueryExecutor(settings)

    def test_resolves_query_specific_param_from_dotenv(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The bug: os.environ didn't have SAP_PARAM_* from .env — must fall back."""
        env_data = 'SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL={"0": "650017"}\n'
        env_file = tmp_path / ".env"
        env_file.write_text(env_data)
        monkeypatch.delenv("SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL", raising=False)

        executor = self._make_executor(tmp_path)
        sql = "WHERE T0.manufSN = '[%0]' AND T0.callType = 2"

        with patch.object(Path, "exists", return_value=True):
            with patch("infrastructure.sap.query_executor.Path") as mock_path_cls:
                mock_path_cls.return_value = env_file
                result = executor._resolve_sql_params(
                    "llamadas_correctivas_serial", sql
                )
        assert "650017" in result
        assert "[%0]" not in result
        assert "PARAM_0" not in result

    def test_param_not_found_returns_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no query-specific or global default, returns PARAM_N fallback."""
        monkeypatch.delenv("SAP_PARAM_UNKNOWN_QUERY", raising=False)
        monkeypatch.delenv("SAP_PARAM_DEFAULT", raising=False)

        executor = self._make_executor(tmp_path=Path("."))
        sql = "WHERE x = '[%0]'"

        with patch.object(Path, "exists", return_value=False):
            result = executor._resolve_sql_params("unknown_query", sql)
        assert result == "WHERE x = 'PARAM_0'"

    def test_uses_global_default_from_dotenv(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Global default SAP_PARAM_DEFAULT from .env is used for unresolves params."""
        env_file = tmp_path / ".env"
        env_file.write_text("SAP_PARAM_DEFAULT=GLOBAL_DEFAULT\n")
        monkeypatch.delenv("SAP_PARAM_DEFAULT", raising=False)
        monkeypatch.delenv("SAP_PARAM_SOME_QUERY", raising=False)

        executor = self._make_executor(tmp_path)
        sql = "WHERE x = '[%0]'"

        with patch.object(Path, "exists", return_value=True):
            with patch("infrastructure.sap.query_executor.Path") as mock_path_cls:
                mock_path_cls.return_value = env_file
                result = executor._resolve_sql_params("some_query", sql)
        assert result == "WHERE x = 'GLOBAL_DEFAULT'"

    def test_no_params_returns_sql_unchanged(self) -> None:
        """When SQL has no [%N] placeholders, return as-is."""
        executor = self._make_executor(tmp_path=Path("."))
        sql = "SELECT * FROM T0 WHERE status = 'open'"
        result = executor._resolve_sql_params("any_query", sql)
        assert result == sql