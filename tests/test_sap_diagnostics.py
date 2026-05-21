from __future__ import annotations

from datetime import datetime, timezone

from infrastructure.sap.diagnostics import build_artifact_paths


def test_build_artifact_paths_is_deterministic_with_fixed_timestamp() -> None:
    fixed_now = datetime(2026, 5, 18, 12, 34, 56, 123456, tzinfo=timezone.utc)

    paths = build_artifact_paths(
        "artifacts/live_debug",
        correlation_id="corr-123",
        stage="login",
        now=fixed_now,
    )

    expected_folder = "20260518T123456123456Z_corr-123_login"
    assert str(paths.screenshot_path).endswith(f"{expected_folder}/page.png")
    assert str(paths.html_path).endswith(f"{expected_folder}/page.html")
