from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

from app.config.runtime import RuntimeContext, ServiceConfig
from app.services.live_service import LiveService


def _build_ctx() -> RuntimeContext:
    cfg = ServiceConfig(
        spring_menus_url="https://spring.example.com/menus",
        spring_image_analysis_url="https://spring.example.com/image-analysis",
        spring_image_identify_url="https://spring.example.com/image-identify",
        spring_text_analysis_url="https://spring.example.com/text-analysis",
        spring_api_token="token-123",
        spring_api_key="key-123",
        gemini_model="gemini-2.5-flash-lite",
        weekly_menu_model="gemini-2.5-flash-lite",
        i18n_locale="en",
        weekly_batch_size=4,
        weekly_sleep_seconds=2.0,
        enable_direct_image_analysis=True,
        timezone_name="Asia/Seoul",
        crawl_weekday=0,
        crawl_hour=6,
        crawl_minute=0,
    )
    return RuntimeContext(config=cfg, client=None)


def test_analyze_food_text_delegates_to_ai_repository():
    svc = LiveService(_build_ctx())

    class StubAIRepo:
        def analyze_food_text(self, client, model_name, food_name):
            assert client is None
            assert model_name == "gemini-2.5-flash-lite"
            assert food_name == "비빔밥"
            return {"foodNameKo": "비빔밥"}

    svc.ai_repo = StubAIRepo()
    out = svc.analyze_food_text("비빔밥")
    assert out["foodNameKo"] == "비빔밥"


def test_build_daily_meals_delegates_to_crawl_repository():
    svc = LiveService(_build_ctx())

    class StubCrawlRepo:
        def load_menu_table_for_source(self, query):
            return {"unused": query}

        def run_weekly_crawl_once(self, cfg, client):
            return {"unused": True}

        def build_daily_meals(self, *, cafeteria_name, table, start, end):
            assert cafeteria_name == "일품식당"
            assert table == {"k": "v"}
            assert start == date(2026, 3, 23)
            assert end == date(2026, 3, 27)
            return [{"mealDate": "2026-03-23", "mealType": "LUNCH", "menus": []}]

    svc.crawl_repo = StubCrawlRepo()
    out = svc.build_daily_meals(
        cafeteria_name="일품식당",
        table={"k": "v"},
        start=date(2026, 3, 23),
        end=date(2026, 3, 27),
    )
    assert out[0]["mealType"] == "LUNCH"


def test_forward_to_spring_uses_token_and_api_key():
    svc = LiveService(_build_ctx())

    class StubSpringRepo:
        def post_json(self, *, url, payload, token, api_key):
            assert url == "https://spring.example.com/ingest"
            assert payload == {"x": 1}
            assert token == "token-123"
            assert api_key == "key-123"
            return {"ok": True}

    svc.spring_repo = StubSpringRepo()
    res = svc.forward_to_spring(url="https://spring.example.com/ingest", payload={"x": 1})
    assert res["ok"] is True


def test_service_supports_dependency_injection_for_repositories():
    ctx = _build_ctx()

    class StubCrawlRepo:
        def run_weekly_crawl_once(self, cfg, client):
            return {"status": "ok"}

        def load_menu_table_for_source(self, query):
            return {"query": query}

        def build_daily_meals(self, *, cafeteria_name, table, start, end):
            return []

    class StubAIRepo:
        def analyze_food_text(self, client, model_name, food_name):
            return {"foodNameKo": food_name}

        def identify_food_from_image(self, client, model_name, image_bytes, mime_type):
            return {"foodNameKo": "테스트"}

        def translate_text(self, client, model_name, source_lang, target_lang, text):
            return "translated"

        def map_ingredient_code(self, token):
            return "EGG"

    class StubSpringRepo:
        def post_json(self, *, url, payload, token, api_key):
            return {"ok": True}

    svc = LiveService(
        ctx,
        crawl_repo=StubCrawlRepo(),
        ai_repo=StubAIRepo(),
        spring_repo=StubSpringRepo(),
    )

    assert svc.run_weekly_crawl_once()["status"] == "ok"
    assert svc.analyze_food_text("계란찜")["foodNameKo"] == "계란찜"


def test_analyze_menus_splits_ingredients_allergies_and_spicy():
    ctx = _build_ctx()

    class StubAIRepo:
        def analyze_food_text(self, client, model_name, food_name):
            return {
                "ingredientsKo": ["달걀"],
                "allergensKo": [{"name": "우유", "reason": "함유 가능"}],
                "spicyLevel": 4,
            }

        def map_ingredient_code(self, token: str):
            t = token.strip()
            if t == "달걀":
                return "EGG"
            if t == "우유":
                return "MILK"
            return None

    svc = LiveService(ctx, ai_repo=StubAIRepo())
    targets = [SimpleNamespace(menuId=99, menuName="테스트")]
    results = asyncio.run(svc.analyze_menus(targets, max_concurrency=2))
    assert len(results) == 1
    row = results[0]
    assert row["status"] == "SUCCESS"
    assert row["spicyLevel"] == 4
    assert row["spicy_level"] == 4
    ing_codes = {x["ingredientCode"] for x in row["ingredients"]}
    assert ing_codes == {"EGG"}
    allergy_codes = {x["allergyCode"] for x in row["allergies"]}
    assert allergy_codes == {"MILK"}
