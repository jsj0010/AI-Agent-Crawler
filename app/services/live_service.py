"""Live 라우터에서 사용하는 서비스 클래스."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from app.config.runtime import RuntimeContext
from app.domain.entities import FoodImageQuery, FoodTextQuery, MenuCrawlQuery, SpringForwardPayload
from app.repositories.ai_repository import AIRepository
from app.repositories.crawl_repository import CrawlRepository
from app.repositories.spring_repository import SpringRepository
from app.services.ops import clamp_spicy_level

logger = logging.getLogger(__name__)
BASE_INGREDIENT_CONFIDENCE = 0.95
INGREDIENT_CONFIDENCE_DECAY = 0.07
MIN_INGREDIENT_CONFIDENCE = 0.5
ALLERGEN_FALLBACK_CONFIDENCE = 0.8


class LiveService:
    """라우터에서 호출할 비즈니스 로직 진입점."""

    def __init__(
        self,
        ctx: RuntimeContext,
        crawl_repo: CrawlRepository | None = None,
        ai_repo: AIRepository | None = None,
        spring_repo: SpringRepository | None = None,
    ):
        self.cfg = ctx.config
        self.client = ctx.client
        self.crawl_repo = crawl_repo or CrawlRepository()
        self.ai_repo = ai_repo or AIRepository()
        self.spring_repo = spring_repo or SpringRepository()

    def run_weekly_crawl_once(self) -> dict[str, Any]:
        return self.crawl_repo.run_weekly_crawl_once(self.cfg, self.client)

    def load_menu_table_for_source(self, cafeteria_name: str, source_url: str):
        query = MenuCrawlQuery(cafeteria_name=cafeteria_name, source_url=source_url)
        return self.crawl_repo.load_menu_table_for_source(query)

    def build_daily_meals(
        self,
        *,
        cafeteria_name: str,
        table: Any,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        return self.crawl_repo.build_daily_meals(
            cafeteria_name=cafeteria_name,
            table=table,
            start=start,
            end=end,
        )

    def analyze_food_text(self, food_name: str) -> dict[str, Any]:
        query = FoodTextQuery(food_name=food_name)
        return self.ai_repo.analyze_food_text(self.client, self.cfg.gemini_model, query.food_name)

    def identify_food_from_image(self, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        query = FoodImageQuery(image_bytes=image_bytes, mime_type=mime_type)
        return self.ai_repo.identify_food_from_image(
            self.client,
            self.cfg.gemini_model,
            query.image_bytes,
            query.mime_type,
        )

    def extract_menu_text_from_image(self, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        query = FoodImageQuery(image_bytes=image_bytes, mime_type=mime_type)
        return self.ai_repo.extract_menu_text_from_image(
            self.client,
            self.cfg.gemini_model,
            query.image_bytes,
            query.mime_type,
        )

    def translate_text(self, source_lang: str, target_lang: str, text: str) -> str:
        return self.ai_repo.translate_text(
            self.client,
            self.cfg.gemini_model,
            source_lang,
            target_lang,
            text,
        )

    def map_ingredient_code(self, token: str) -> str | None:
        return self.ai_repo.map_ingredient_code(token)

    def forward_to_spring(
        self,
        *,
        url: str,
        payload: dict[str, Any],
    ) -> requests.Response:
        forward = SpringForwardPayload(url=url, payload=payload)
        return self.spring_repo.post_json(
            url=forward.url,
            payload=forward.payload,
            token=self.cfg.spring_api_token,
            api_key=self.cfg.spring_api_key,
        )

    async def analyze_menus(
        self,
        menus: list[Any],
        *,
        max_concurrency: int = 4,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _analyze_single_menu(target) -> dict[str, Any]:
            # Spring LocalDateTime 호환(타임존 오프셋 없이 로컬 벽시계)
            analyzed_at = datetime.now(ZoneInfo(self.cfg.timezone_name)).strftime("%Y-%m-%dT%H:%M:%S")
            try:
                async with semaphore:
                    analysis = await asyncio.to_thread(self.analyze_food_text, target.menuName)
                ingredient_codes: list[dict[str, Any]] = []
                ing_dedup: set[str] = set()
                for idx, ingredient in enumerate(analysis.get("ingredientsKo") or []):
                    code = self.map_ingredient_code(str(ingredient).strip())
                    if not code or code in ing_dedup:
                        continue
                    ing_dedup.add(code)
                    ingredient_codes.append(
                        {
                            "ingredientCode": code,
                            "confidence": round(
                                max(
                                    MIN_INGREDIENT_CONFIDENCE,
                                    BASE_INGREDIENT_CONFIDENCE - (idx * INGREDIENT_CONFIDENCE_DECAY),
                                ),
                                2,
                            ),
                        }
                    )
                allergy_codes: list[dict[str, Any]] = []
                allergy_dedup: set[str] = set()
                for allergen in analysis.get("allergensKo") or []:
                    if not isinstance(allergen, dict):
                        continue
                    code = self.map_ingredient_code(str(allergen.get("name", "")).strip())
                    if not code or code in allergy_dedup:
                        continue
                    allergy_dedup.add(code)
                    allergy_codes.append(
                        {"allergyCode": code, "confidence": ALLERGEN_FALLBACK_CONFIDENCE}
                    )
                spicy = clamp_spicy_level(
                    analysis.get("spicyLevel") if analysis.get("spicyLevel") is not None else analysis.get("spicy_level")
                )
                return {
                    "menuId": target.menuId,
                    "menuName": target.menuName,
                    "status": "SUCCESS",
                    "reason": None,
                    "modelName": "gemini",
                    "modelVersion": self.cfg.gemini_model,
                    "analyzedAt": analyzed_at,
                    "spicyLevel": spicy,
                    "spicy_level": spicy,
                    "ingredients": ingredient_codes,
                    "allergies": allergy_codes,
                }
            except Exception as e:
                return {
                    "menuId": target.menuId,
                    "menuName": target.menuName,
                    "status": "FAILED",
                    "reason": str(e)[:300],
                    "modelName": "gemini",
                    "modelVersion": self.cfg.gemini_model,
                    "analyzedAt": analyzed_at,
                    "spicyLevel": None,
                    "spicy_level": None,
                    "ingredients": [],
                    "allergies": [],
                }

        return await asyncio.gather(*[_analyze_single_menu(target) for target in menus])

    async def translate_menus(
        self,
        menus: list[Any],
        *,
        target_languages: list[str],
        max_concurrency: int = 4,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _translate_single_menu(menu) -> dict[str, Any]:
            translations: list[dict[str, str]] = []
            translation_errors: list[dict[str, str]] = []

            async def _translate_one_language(lang: str) -> tuple[str, str | None, str | None]:
                lang_code = lang.strip()
                if not lang_code:
                    return "", None, None
                try:
                    async with semaphore:
                        translated = await asyncio.to_thread(
                            self.translate_text,
                            "ko",
                            lang_code,
                            menu.menuName,
                        )
                    return lang_code, translated, None
                except Exception as e:
                    return lang_code, None, str(e)

            results_by_lang = await asyncio.gather(
                *[_translate_one_language(lang) for lang in target_languages]
            )
            for lang_code, translated, error_reason in results_by_lang:
                if not lang_code:
                    continue
                if translated is not None:
                    translations.append({"langCode": lang_code, "translatedName": translated})
                    continue
                if error_reason is not None:
                    logger.warning("translation failed menuId=%s lang=%s: %s", menu.menuId, lang_code, error_reason)
                    translation_errors.append({"langCode": lang_code, "reason": error_reason})
            return {
                "menuId": menu.menuId,
                "sourceName": menu.menuName,
                "translations": translations,
                "translationErrors": translation_errors,
            }

        return await asyncio.gather(*[_translate_single_menu(menu) for menu in menus])
