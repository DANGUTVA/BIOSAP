from __future__ import annotations

from contextlib import nullcontext

from interfaces.streamlit.pages import pipeline as pipeline_page


class _FailingPipeline:
    def execute(self, query_id: str, correlation_id: str) -> dict[str, object]:
        raise RuntimeError(
            "SAP query failed for query_id=sales_by_customer. "
            "debug_artifacts=screenshot:artifacts/live_debug/a/page.png,html:artifacts/live_debug/a/page.html"
        )


class _Catalog:
    def list_queries(self) -> list[dict[str, str]]:
        return [{"id": "sales_by_customer"}]


def test_pipeline_page_catches_exception_and_renders_error(monkeypatch) -> None:
    calls: dict[str, list[str]] = {"error": [], "text": []}

    monkeypatch.setattr(pipeline_page.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline_page.st, "selectbox", lambda *_args, **_kwargs: "sales_by_customer")
    monkeypatch.setattr(pipeline_page.st, "button", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline_page.st, "error", lambda message: calls["error"].append(message))
    monkeypatch.setattr(pipeline_page.st, "text", lambda message: calls["text"].append(message))
    monkeypatch.setattr(pipeline_page.st, "expander", lambda *_args, **_kwargs: nullcontext())

    services = {"catalog": _Catalog(), "pipeline": _FailingPipeline()}

    pipeline_page.render(services)

    assert len(calls["error"]) == 1
    assert "Likely cause" in calls["error"][0]
    assert any("artifacts/live_debug" in item for item in calls["text"])
