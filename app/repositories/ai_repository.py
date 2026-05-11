"""Gemini 호출/재료 코드 매핑 Repository."""

from __future__ import annotations

from google import genai

from app.common.service_ops import (
    analyze_food_text,
    extract_menu_text_from_image,
    identify_food_from_image,
    map_ingredient_code,
    translate_text_with_gemini,
)


class AIRepository:
    """Gemini 호출/재료 코드 매핑 Repository."""

    def analyze_food_text(self, client: genai.Client | None, model_name: str, food_name: str) -> dict:
        return analyze_food_text(client, model_name, food_name)

    def identify_food_from_image(
        self,
        client: genai.Client | None,
        model_name: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        return identify_food_from_image(client, model_name, image_bytes, mime_type)

    def extract_menu_text_from_image(
        self,
        client: genai.Client | None,
        model_name: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        return extract_menu_text_from_image(client, model_name, image_bytes, mime_type)

    def translate_text(
        self,
        client: genai.Client | None,
        model_name: str,
        source_lang: str,
        target_lang: str,
        text: str,
    ) -> str:
        return translate_text_with_gemini(client, model_name, source_lang, target_lang, text)

    def map_ingredient_code(self, token: str) -> str | None:
        return map_ingredient_code(token)
