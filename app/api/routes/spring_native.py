"""Spring WebClient가 직접 파싱하는 비래핑(unwrapped) 엔드포인트."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests
from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from app.config.runtime import API_V1_PREFIX, RuntimeContext
from app.schemas.api_models import PythonMealCrawlRequest, PythonMenuAnalysisRequest
from app.services.live_service import LiveService
from app.common.service_ops import (
    CrawlSourceUpstreamError,
    sanitize_url_for_log,
    v1_error,
    v1_success,
    validate_accept_language,
)

logger = logging.getLogger(__name__)


class FreeTranslationRequest(BaseModel):
    sourceLang: str = Field(..., min_length=1)
    targetLang: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


def create_spring_native_router(ctx: RuntimeContext) -> APIRouter:
    service = LiveService(ctx)
    cfg = service.cfg
    client = service.client
    router = APIRouter(prefix=API_V1_PREFIX)

    @router.post(
        "/crawl/meals",
        tags=["spring-native"],
        summary="식단 크롤링 (unwrapped)",
        operation_id="springNativeCrawlMeals",
    )
    def crawl_meals_native(
        request: Request,
        payload: PythonMealCrawlRequest = Body(...),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return v1_error("COM_001", str(e), status_code=400)

        try:
            table = service.load_menu_table_for_source(payload.cafeteriaName, payload.sourceUrl)
        except RuntimeError as e:
            logger.warning("crawl bad request cafeteria=%s reason=%s", payload.cafeteriaName, e)
            return v1_error("PYM_400", "요청 식단 조회 조건이 유효하지 않거나 데이터가 없습니다.", status_code=400)
        except (CrawlSourceUpstreamError, requests.exceptions.RequestException, OSError) as e:
            logger.warning(
                "upstream crawl source unavailable source=%s cafeteriaName=%s: %s",
                sanitize_url_for_log(payload.sourceUrl),
                payload.cafeteriaName,
                e,
            )
            return v1_error("PYM_502", "외부 크롤링 소스 조회에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=502)

        meals = service.build_daily_meals(
            cafeteria_name=payload.cafeteriaName,
            table=table,
            start=payload.startDate,
            end=payload.endDate,
        )
        return {
            "schoolName": payload.schoolName,
            "cafeteriaName": payload.cafeteriaName,
            "sourceUrl": payload.sourceUrl,
            "startDate": payload.startDate.isoformat(),
            "endDate": payload.endDate.isoformat(),
            "meals": meals,
        }

    @router.post(
        "/menus/analyze",
        tags=["spring-native"],
        summary="메뉴 AI 분석 (unwrapped)",
        operation_id="springNativeAnalyzeMenus",
    )
    async def analyze_menus_native(
        request: Request,
        payload: PythonMenuAnalysisRequest = Body(...),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return v1_error("COM_001", str(e), status_code=400)
        if client is None:
            return v1_error("AI_001", "AI 서비스가 구성되지 않았습니다.", status_code=500)

        results = await service.analyze_menus(payload.menus, max_concurrency=cfg.ai_max_concurrent_tasks)
        return {"results": results}

    @router.post(
        "/translations",
        tags=["spring-native"],
        summary="자유 텍스트 번역",
        operation_id="springNativeTranslateText",
    )
    async def translate_text_native(
        request: Request,
        payload: FreeTranslationRequest = Body(...),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return v1_error("COM_001", str(e), status_code=400)
        if client is None:
            return v1_error("AI_001", "AI 서비스가 구성되지 않았습니다.", status_code=500)

        translated = await asyncio.to_thread(
            service.translate_text,
            payload.sourceLang,
            payload.targetLang,
            payload.text,
        )
        return v1_success({"translatedText": translated})

    return router
