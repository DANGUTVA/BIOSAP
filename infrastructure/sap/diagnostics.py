"""Utilities to persist live SAP troubleshooting artifacts (async)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SapDebugArtifactPaths:
    """File paths for a single diagnostic capture."""

    screenshot_path: Path
    html_path: Path


def _sanitize(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def build_artifact_paths(
    base_path: str,
    correlation_id: str,
    stage: str,
    *,
    now: datetime | None = None,
) -> SapDebugArtifactPaths:
    """Build deterministic artifact paths for screenshot and HTML capture."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(base_path) / f"{stamp}_{_sanitize(correlation_id)}_{_sanitize(stage)}"
    return SapDebugArtifactPaths(
        screenshot_path=folder / "page.png",
        html_path=folder / "page.html",
    )


async def capture_page_artifacts(page: object, artifact_paths: SapDebugArtifactPaths) -> SapDebugArtifactPaths:
    """Capture screenshot and HTML if possible, creating destination folder."""
    artifact_paths.screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    screenshot_error: Exception | None = None
    html_error: Exception | None = None

    try:
        await page.screenshot(path=str(artifact_paths.screenshot_path), full_page=True)
    except Exception as exc:  # pragma: no cover - best effort capture
        screenshot_error = exc

    try:
        content = await page.content()
        artifact_paths.html_path.write_text(content, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best effort capture
        html_error = exc

    if screenshot_error and html_error:
        raise RuntimeError(
            f"Failed to save diagnostics screenshot ({screenshot_error}) and html ({html_error})"
        ) from html_error

    return artifact_paths
