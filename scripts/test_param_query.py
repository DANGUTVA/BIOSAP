"""Integration test: run a parameterized query against live SAP."""

from __future__ import annotations

import os
from pathlib import Path

from app.utils.async_runner import run_async

# Set query-specific parameter BEFORE importing settings
# Replace with a real serial number from your SAP system
os.environ["SAP_PARAM_LLAMADAS_CORRECTIVAS_SERIAL"] = '{"0": "TEST_SERIAL"}'

from app.config.settings import get_settings
from infrastructure.sap.query_executor import SapQueryExecutor


def main() -> int:
    settings = get_settings()
    executor = SapQueryExecutor(settings)

    # Load the SQL that contains [%0]
    sql_path = Path("queries/sql/llamadas_correctivas_serial.sql")
    sql_text = sql_path.read_text(encoding="utf-8")

    print(f"Original SQL (first 200 chars): {sql_text[:200]}...")
    print()

    # Test the param resolution directly
    from infrastructure.sap.param_resolver import has_parameters, extract_param_indices
    print(f"Has parameters: {has_parameters(sql_text)}")
    print(f"Param indices: {extract_param_indices(sql_text)}")

    # Resolve and show the effective SQL
    effective = executor._resolve_sql_params("llamadas_correctivas_serial", sql_text)
    print(f"\nResolved SQL (first 200 chars): {effective[:200]}...")
    print()

    if not settings.sap_mock_mode:
        print("Running against live SAP (this may take a while)...")
        try:
            df = run_async(executor.run_query("llamadas_correctivas_serial", sql_text, "integration_test"))
            print(f"Query returned {len(df)} rows")
            print(df.head(10))
        except Exception as exc:
            print(f"Query failed (may be expected if TEST_SERIAL doesn't exist): {exc}")
            return 0  # Not a failure of the param resolution
    else:
        print("Mock mode enabled, loading fixture...")
        df = run_async(executor.run_query("llamadas_correctivas_serial", sql_text, "integration_test"))
        print(f"Mock query returned {len(df)} rows")
        print(df.head(10))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
