"""Live service 런타임 설정/컨텍스트."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google import genai

WEEKDAY_TO_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
API_V1_PREFIX = "/api/v1"
ALLOWED_ACCEPT_LANGUAGES = {"ko", "en", "zh-CN", "vi", "ja"}
CANONICAL_TO_INGREDIENT_CODE = {
    "난류": "EGG",
    "우유": "MILK",
    "메밀": "BUCKWHEAT",
    "땅콩": "PEANUT",
    "대두": "SOYBEAN",
    "밀": "WHEAT",
    "고등어": "MACKEREL",
    "게": "CRAB",
    "새우": "SHRIMP",
    "돼지고기": "PORK",
    "복숭아": "PEACH",
    "토마토": "TOMATO",
    "아황산류": "SULFITE",
    "호두": "WALNUT",
    "닭고기": "CHICKEN",
    "쇠고기": "BEEF",
    "오징어": "SQUID",
    "조개류": "SHELLFISH",
    "조개": "CLAM",
    "홍합": "MUSSEL",
    "굴": "OYSTER",
    "랍스터": "LOBSTER",
    "가리비": "SCALLOP",
    "잣": "PINE_NUT",
    "귀리": "OATS",
    "호밀": "RYE",
    "보리": "BARLEY",
    "견과류": "TREE_NUT",
    "아몬드": "ALMOND",
    "헤이즐넛": "HAZELNUT",
    "캐슈너트": "CASHEW",
    "피스타치오": "PISTACHIO",
    "피칸": "PECAN",
    "브라질너트": "BRAZIL_NUT",
    "마카다미아": "MACADAMIA",
    "망고": "MANGO",
    "아보카도": "AVOCADO",
    "바나나": "BANANA",
    "키위": "KIWI",
    "셀러리": "CELERY",
    "머스타드": "MUSTARD",
    "아황산": "SULFITES",
    "아황산류": "SULFITES",
    "참깨": "SESAME",
    "루핀": "LUPIN",
    "라텍스": "LATEX_RELATED",
}


@dataclass
class ServiceConfig:
    spring_menus_url: str | None
    spring_image_analysis_url: str | None
    spring_image_identify_url: str | None
    spring_text_analysis_url: str | None
    spring_api_token: str | None
    spring_api_key: str | None
    gemini_model: str
    weekly_menu_model: str
    i18n_locale: str
    weekly_batch_size: int
    weekly_sleep_seconds: float
    enable_direct_image_analysis: bool
    timezone_name: str
    crawl_weekday: int
    crawl_hour: int
    crawl_minute: int
    ai_max_concurrent_tasks: int = 4


@dataclass
class RuntimeContext:
    config: ServiceConfig
    client: genai.Client | None


def load_config() -> ServiceConfig:
    weekday_text = os.environ.get("WEEKLY_CRAWL_DAY", "mon").strip().lower()
    if weekday_text not in WEEKDAY_TO_INDEX:
        raise RuntimeError("WEEKLY_CRAWL_DAY must be one of mon,tue,wed,thu,fri,sat,sun")
    raw_hour = os.environ.get("WEEKLY_CRAWL_HOUR", "6")
    raw_minute = os.environ.get("WEEKLY_CRAWL_MINUTE", "0")
    try:
        hour = int(raw_hour)
        minute = int(raw_minute)
    except ValueError as e:
        raise RuntimeError("WEEKLY_CRAWL_HOUR/WEEKLY_CRAWL_MINUTE must be integers (hour: 0..23, minute: 0..59)") from e
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RuntimeError("WEEKLY_CRAWL_HOUR/MINUTE out of range")
    raw_batch_size = os.environ.get("WEEKLY_MENU_BATCH_SIZE", "4")
    raw_sleep_seconds = os.environ.get("WEEKLY_MENU_SLEEP_SECONDS", "21.0")
    try:
        weekly_batch_size = int(raw_batch_size)
    except ValueError as e:
        raise RuntimeError("WEEKLY_MENU_BATCH_SIZE must be an integer >= 1") from e
    if weekly_batch_size < 1:
        raise RuntimeError("WEEKLY_MENU_BATCH_SIZE must be >= 1")
    try:
        weekly_sleep_seconds = float(raw_sleep_seconds)
    except ValueError as e:
        raise RuntimeError("WEEKLY_MENU_SLEEP_SECONDS must be a float >= 0") from e
    if weekly_sleep_seconds < 0:
        raise RuntimeError("WEEKLY_MENU_SLEEP_SECONDS must be >= 0")
    timezone_name = os.environ.get("SERVICE_TIMEZONE", "Asia/Seoul").strip() or "Asia/Seoul"
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as e:
        raise RuntimeError(f"SERVICE_TIMEZONE is invalid: {timezone_name}") from e
    enable_direct_image_analysis = (
        os.environ.get("ENABLE_DIRECT_IMAGE_ANALYSIS", "false").strip().lower() == "true"
    )
    raw_ai_concurrency = os.environ.get("AI_MAX_CONCURRENT_TASKS", "4")
    try:
        ai_max_concurrent_tasks = int(raw_ai_concurrency)
    except ValueError as e:
        raise RuntimeError("AI_MAX_CONCURRENT_TASKS must be an integer >= 1") from e
    if ai_max_concurrent_tasks < 1:
        raise RuntimeError("AI_MAX_CONCURRENT_TASKS must be >= 1")
    return ServiceConfig(
        spring_menus_url=os.environ.get("SPRING_MENUS_URL", "").strip() or None,
        spring_image_analysis_url=os.environ.get("SPRING_IMAGE_ANALYSIS_URL", "").strip() or None,
        spring_image_identify_url=os.environ.get("SPRING_IMAGE_IDENTIFY_URL", "").strip() or None,
        spring_text_analysis_url=os.environ.get("SPRING_TEXT_ANALYSIS_URL", "").strip() or None,
        spring_api_token=os.environ.get("SPRING_API_TOKEN", "").strip() or None,
        spring_api_key=os.environ.get("SPRING_API_KEY", "").strip() or None,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        weekly_menu_model=os.environ.get("WEEKLY_MENU_MODEL", "gemini-2.5-flash-lite"),
        i18n_locale=os.environ.get("I18N_LOCALE", "en"),
        weekly_batch_size=weekly_batch_size,
        weekly_sleep_seconds=weekly_sleep_seconds,
        enable_direct_image_analysis=enable_direct_image_analysis,
        timezone_name=timezone_name,
        crawl_weekday=WEEKDAY_TO_INDEX[weekday_text],
        crawl_hour=hour,
        crawl_minute=minute,
        ai_max_concurrent_tasks=ai_max_concurrent_tasks,
    )


def load_runtime_context() -> RuntimeContext:
    config = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    client = genai.Client(api_key=api_key) if api_key else None
    return RuntimeContext(config=config, client=client)
