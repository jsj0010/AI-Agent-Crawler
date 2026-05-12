"""Gemini(AI)를 사용하는 HTTP API 통합 테스트.

`GEMINI_API_KEY`가 없으면 스킵합니다. 실제 호출은 네트워크가 필요합니다.
로컬에서: `GEMINI_API_KEY=... pytest tests/integration/test_ai_agent_api.py -v`
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import repo_env

repo_env.load_dotenv_from_repo_root()

from app.config.app_factory import create_app
from app.config.runtime import load_runtime_context

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY", "").strip(),
    reason="GEMINI_API_KEY 없음 — .env 또는 환경변수로 설정 후 다시 실행하세요.",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(create_app(load_runtime_context())) as tc:
        yield tc


def test_python_menus_analyze_returns_success_data(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/python/menus/analyze",
        json={"menus": [{"menuId": 101, "menuName": "김치찌개"}]},
        headers={"Accept-Language": "ko"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    data = body.get("data") or {}
    assert "results" in data
    assert len(data["results"]) >= 1
    first = data["results"][0]
    assert first.get("menuId") == 101
    assert first.get("status") in ("COMPLETED", "FAILED")
    if first.get("status") == "COMPLETED":
        assert isinstance(first.get("ingredients"), list)


def test_python_menus_translate_returns_success_data(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/python/menus/translate",
        json={
            "menus": [{"menuId": 202, "menuName": "된장찌개"}],
            "targetLanguages": ["en"],
        },
        headers={"Accept-Language": "ko"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    data = body.get("data") or {}
    assert "results" in data
    assert len(data["results"]) >= 1
    row = data["results"][0]
    assert row.get("menuId") == 202
    assert any(t.get("langCode") == "en" for t in (row.get("translations") or []))


def test_spring_native_menus_analyze_unwrapped(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/menus/analyze",
        json={"menus": [{"menuId": 303, "menuName": "비빔밥"}]},
        headers={"Accept-Language": "ko"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "success" not in body
    assert "results" in body
    assert len(body["results"]) >= 1


def test_free_translation_returns_success_data(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/translations",
        json={"sourceLang": "ko", "targetLang": "en", "text": "이 메뉴에 땅콩이 들어가나요?"},
        headers={"Accept-Language": "ko"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "translatedText" in body
