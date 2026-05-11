"""FastAPI `/api/v1` 라우터 (식단/분석/번역 3개 API만 제공)."""

from __future__ import annotations

import logging

import requests
from fastapi import APIRouter, Body, Request

from app.config.runtime import API_V1_PREFIX, RuntimeContext
from app.schemas.api_models import (
    ApiErrorResponse,
    ApiSuccessResponse,
    PythonMealCrawlResponse,
    PythonMealCrawlRequest,
    PythonMenuAnalysisResponse,
    PythonMenuAnalysisRequest,
    PythonMenuTranslationResponse,
    PythonMenuTranslationRequest,
)
from app.schemas.openapi_examples import (
    AI_KEY_MISSING_EXAMPLE,
    MEAL_CRAWL_ERROR_BAD_CONDITION_EXAMPLE,
    MEAL_CRAWL_ERROR_UPSTREAM_EXAMPLE,
    MEAL_CRAWL_REQUEST_OPENAPI_EXAMPLES,
    MEAL_CRAWL_SUCCESS_EXAMPLE,
    MENU_ANALYZE_REQUEST_OPENAPI_EXAMPLES,
    MENU_ANALYZE_SUCCESS_EXAMPLE,
    MENU_TRANSLATE_REQUEST_OPENAPI_EXAMPLES,
    MENU_TRANSLATE_SUCCESS_EXAMPLE,
    VALIDATION_ERROR_EXAMPLE,
    V1_INTERNAL_SERVER_ERROR_EXAMPLE,
)
from app.services.live_service import LiveService
from app.common.service_ops import (
    CrawlSourceUpstreamError,
    sanitize_url_for_log,
    v1_error,
    v1_success,
    validate_accept_language,
)

logger = logging.getLogger(__name__)


def _v1_bad_request(msg: str):
    return v1_error("COM_001", msg, status_code=400)


def create_v1_router(ctx: RuntimeContext) -> APIRouter:
    service = LiveService(ctx)
    cfg = service.cfg
    client = service.client
    router = APIRouter(prefix=API_V1_PREFIX)

    @router.post(
        "/python/meals/crawl",
        tags=["v1"],
        summary="식단 기간 조회/크롤링",
        description="학교/식당/기간 조건으로 식단을 조회하고 메뉴 목록을 표준 DTO로 반환합니다.",
        operation_id="crawlMealsV1",
        response_model=ApiSuccessResponse[PythonMealCrawlResponse],
        responses={
            200: {
                "description": "조회 성공",
                "content": {
                    "application/json": {
                        "examples": {
                            "식단포함": {
                                "summary": "meals에 일자별 메뉴 포함",
                                "value": MEAL_CRAWL_SUCCESS_EXAMPLE,
                            }
                        }
                    }
                },
            },
            400: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "검증실패": {"summary": "스키마/헤더 검증 오류", "value": VALIDATION_ERROR_EXAMPLE},
                            "조건불가": {
                                "summary": "식당/URL 조건 오류",
                                "value": MEAL_CRAWL_ERROR_BAD_CONDITION_EXAMPLE,
                            },
                        }
                    }
                },
            },
            502: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "업스트림실패": {"summary": "외부 크롤 소스 실패", "value": MEAL_CRAWL_ERROR_UPSTREAM_EXAMPLE},
                        }
                    }
                },
            },
            500: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "서버오류": {
                                "summary": "처리 중 내부 오류(문서 예시)",
                                "value": V1_INTERNAL_SERVER_ERROR_EXAMPLE,
                            },
                        }
                    }
                },
            },
        },
    )
    def crawl_meals_v1(
        request: Request,
        payload: PythonMealCrawlRequest = Body(..., openapi_examples=MEAL_CRAWL_REQUEST_OPENAPI_EXAMPLES),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return _v1_bad_request(str(e))
        if payload.startDate > payload.endDate:
            return _v1_bad_request("startDate는 endDate보다 이후일 수 없습니다.")
        try:
            table = service.load_menu_table_for_source(payload.cafeteriaName, payload.sourceUrl)
        except RuntimeError as e:
            logger.warning("crawl bad request cafeteria=%s reason=%s", payload.cafeteriaName, e)
            return v1_error("PYM_400", "요청 식단 조회 조건이 유효하지 않거나 데이터가 없습니다.", status_code=400)
        except (CrawlSourceUpstreamError, requests.exceptions.RequestException, OSError) as e:
            logger.warning("upstream crawl source unavailable source=%s cafeteriaName=%s: %s", sanitize_url_for_log(payload.sourceUrl), payload.cafeteriaName, e)
            return v1_error("PYM_502", "외부 크롤링 소스 조회에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=502)
        meals = service.build_daily_meals(cafeteria_name=payload.cafeteriaName, table=table, start=payload.startDate, end=payload.endDate)
        return v1_success({"schoolName": payload.schoolName, "cafeteriaName": payload.cafeteriaName, "sourceUrl": payload.sourceUrl, "startDate": payload.startDate.isoformat(), "endDate": payload.endDate.isoformat(), "meals": meals})

    @router.post(
        "/python/menus/analyze",
        tags=["v1"],
        summary="메뉴 텍스트 AI 분석",
        description="메뉴명 리스트를 받아 재료 코드/신뢰도 추정 결과를 반환합니다.",
        operation_id="analyzeMenusV1",
        response_model=ApiSuccessResponse[PythonMenuAnalysisResponse],
        responses={
            200: {
                "description": "분석 성공",
                "content": {
                    "application/json": {
                        "examples": {
                            "재료추정": {"summary": "ingredients 포함", "value": MENU_ANALYZE_SUCCESS_EXAMPLE},
                        }
                    }
                },
            },
            400: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "검증실패": {"value": VALIDATION_ERROR_EXAMPLE},
                        }
                    }
                },
            },
            500: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "키미설정": {"summary": "GEMINI 미설정", "value": AI_KEY_MISSING_EXAMPLE},
                        }
                    }
                },
            },
        },
    )
    async def analyze_menus_v1(
        request: Request,
        payload: PythonMenuAnalysisRequest = Body(..., openapi_examples=MENU_ANALYZE_REQUEST_OPENAPI_EXAMPLES),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return _v1_bad_request(str(e))
        if client is None:
            return v1_error("AI_001", "GEMINI_API_KEY is not set", status_code=500)
        results = await service.analyze_menus(payload.menus, max_concurrency=cfg.ai_max_concurrent_tasks)
        return v1_success({"results": results})

    @router.post(
        "/python/menus/translate",
        tags=["v1"],
        summary="메뉴 다국어 번역",
        description="메뉴명 리스트를 요청 언어 목록으로 번역해 반환합니다.",
        operation_id="translateMenusV1",
        response_model=ApiSuccessResponse[PythonMenuTranslationResponse],
        responses={
            200: {
                "description": "번역 성공",
                "content": {
                    "application/json": {
                        "examples": {
                            "다국어": {"summary": "translations 배열", "value": MENU_TRANSLATE_SUCCESS_EXAMPLE},
                        }
                    }
                },
            },
            400: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "검증실패": {"value": VALIDATION_ERROR_EXAMPLE},
                        }
                    }
                },
            },
            500: {
                "model": ApiErrorResponse,
                "content": {
                    "application/json": {
                        "examples": {
                            "키미설정": {"value": AI_KEY_MISSING_EXAMPLE},
                        }
                    }
                },
            },
        },
    )
    async def translate_menus_v1(
        request: Request,
        payload: PythonMenuTranslationRequest = Body(..., openapi_examples=MENU_TRANSLATE_REQUEST_OPENAPI_EXAMPLES),
    ):
        try:
            validate_accept_language(request.headers.get("Accept-Language"))
        except ValueError as e:
            return _v1_bad_request(str(e))
        if client is None:
            return v1_error("AI_001", "GEMINI_API_KEY is not set", status_code=500)
        results = await service.translate_menus(
            payload.menus,
            target_languages=payload.targetLanguages,
            max_concurrency=cfg.ai_max_concurrent_tasks,
        )
        return v1_success({"results": results})

    return router
