"""Spring `PythonMealClientAdapter`가 파싱하는 비래핑 응답 계약."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config.app_factory import create_app
from app.config.runtime import load_runtime_context


def test_spring_native_crawl_meals_returns_unwrapped_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_load(self, cafeteria_name: str, source_url: str):
        return pd.DataFrame()

    monkeypatch.setattr(
        "app.services.live_service.LiveService.load_menu_table_for_source",
        _fake_load,
    )
    with TestClient(create_app(load_runtime_context())) as client:
        resp = client.post(
            "/api/v1/crawl/meals",
            json={
                "schoolName": "금오공과대학교",
                "cafeteriaName": "학생식당",
                "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
                "startDate": "2026-04-21",
                "endDate": "2026-04-27",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "success" not in body
    assert body["schoolName"] == "금오공과대학교"
    assert body["cafeteriaName"] == "일품식당"
    assert "startDate" in body and "endDate" in body
    assert body["meals"] == []


def test_spring_native_crawl_invalid_range_returns_400() -> None:
    with TestClient(create_app(load_runtime_context())) as client:
        resp = client.post(
            "/api/v1/crawl/meals",
            json={
                "schoolName": "금오공과대학교",
                "cafeteriaName": "학생식당",
                "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
                "startDate": "2026-05-10",
                "endDate": "2026-05-01",
            },
        )
    assert resp.status_code == 400
    body = resp.json()
    assert "message" in body or (body.get("success") is False and body.get("code"))
