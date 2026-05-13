"""Live service의 순수 비즈니스 로직 모듈."""

from __future__ import annotations

import json
import logging
import os
import re
import socket
from datetime import date, datetime, timedelta
from io import StringIO
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pandas.errors import ParserError

from app.config.runtime import ALLOWED_ACCEPT_LANGUAGES, CANONICAL_TO_INGREDIENT_CODE, ServiceConfig
from app.domain.allergy.agent import analyze_menus_with_gemini, iter_menu_entries, results_to_dataframe
from app.domain.crawler.kumoh_menu import MENU_ITEM_DELIM, load_menus, normalize_kumoh_cafeteria_name, parse_table_from_html
from app.domain.crawler.push_menus import post_menu_ingest
from user_features.allergen_catalog import ALIAS_TO_CANONICAL
from user_features.i18n_summary import summarize_for_locale
from user_features.payloads import build_extended_menu_payload

DEFAULT_SOURCE_ALLOWLIST = {"www.kumoh.ac.kr", "kumoh.ac.kr"}
MEAL_TYPE_ORDER = {"BREAKFAST": 0, "LUNCH": 1, "DINNER": 2}
logger = logging.getLogger(__name__)

SPICY_LEVEL_MIN = 0
SPICY_LEVEL_MAX = 5


def clamp_spicy_level(raw: Any) -> int:
    """모델·JSON의 spicyLevel 값을 0~5 정수로 맞춘다. 공통 유틸."""
    if raw is None:
        return SPICY_LEVEL_MIN
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        return SPICY_LEVEL_MIN
    return max(SPICY_LEVEL_MIN, min(SPICY_LEVEL_MAX, n))
ALLERGY_KEYWORD_TO_API_CODE = {
    "mackerel": "MACKEREL",
    "고등어": "MACKEREL",
    "crab": "CRAB",
    "게": "CRAB",
    "shrimp": "SHRIMP",
    "새우": "SHRIMP",
    "squid": "SQUID",
    "오징어": "SQUID",
    "shellfish": "SHELLFISH",
    "조개류": "SHELLFISH",
    "clam": "CLAM",
    "조개": "CLAM",
    "mussel": "MUSSEL",
    "홍합": "MUSSEL",
    "oyster": "OYSTER",
    "굴": "OYSTER",
    "lobster": "LOBSTER",
    "랍스터": "LOBSTER",
    "scallop": "SCALLOP",
    "가리비": "SCALLOP",
    "pork": "PORK",
    "돼지고기": "PORK",
    "돼지": "PORK",
    "제육": "PORK",
    "chicken": "CHICKEN",
    "닭고기": "CHICKEN",
    "닭": "CHICKEN",
    "치킨": "CHICKEN",
    "beef": "BEEF",
    "쇠고기": "BEEF",
    "소고기": "BEEF",
    "egg": "EGG",
    "난류": "EGG",
    "계란": "EGG",
    "달걀": "EGG",
    "milk": "MILK",
    "dairy": "MILK",
    "우유": "MILK",
    "유제품": "MILK",
    "peanut": "PEANUT",
    "땅콩": "PEANUT",
    "soybean": "SOYBEAN",
    "soy": "SOYBEAN",
    "대두": "SOYBEAN",
    "wheat": "WHEAT",
    "밀": "WHEAT",
    "buckwheat": "BUCKWHEAT",
    "메밀": "BUCKWHEAT",
    "oats": "OATS",
    "귀리": "OATS",
    "rye": "RYE",
    "호밀": "RYE",
    "barley": "BARLEY",
    "보리": "BARLEY",
    "tree nut": "TREE_NUT",
    "tree nuts": "TREE_NUT",
    "견과류": "TREE_NUT",
    "walnut": "WALNUT",
    "호두": "WALNUT",
    "almond": "ALMOND",
    "아몬드": "ALMOND",
    "hazelnut": "HAZELNUT",
    "헤이즐넛": "HAZELNUT",
    "cashew": "CASHEW",
    "캐슈너트": "CASHEW",
    "pistachio": "PISTACHIO",
    "피스타치오": "PISTACHIO",
    "pecan": "PECAN",
    "피칸": "PECAN",
    "brazil nut": "BRAZIL_NUT",
    "브라질너트": "BRAZIL_NUT",
    "macadamia": "MACADAMIA",
    "마카다미아": "MACADAMIA",
    "pine nut": "PINE_NUT",
    "잣": "PINE_NUT",
    "peach": "PEACH",
    "복숭아": "PEACH",
    "mango": "MANGO",
    "망고": "MANGO",
    "avocado": "AVOCADO",
    "아보카도": "AVOCADO",
    "banana": "BANANA",
    "바나나": "BANANA",
    "kiwi": "KIWI",
    "키위": "KIWI",
    "tomato": "TOMATO",
    "토마토": "TOMATO",
    "celery": "CELERY",
    "셀러리": "CELERY",
    "mustard": "MUSTARD",
    "머스타드": "MUSTARD",
    "sulfites": "SULFITES",
    "아황산류": "SULFITES",
    "sesame": "SESAME",
    "참깨": "SESAME",
    "lupin": "LUPIN",
    "루핀": "LUPIN",
    "latex": "LATEX_RELATED",
    "라텍스": "LATEX_RELATED",
}
ALLERGY_API_CODES = set(ALLERGY_KEYWORD_TO_API_CODE.values())


class CrawlSourceUpstreamError(Exception):
    """외부 sourceUrl fetch/파싱 실패가 최종적으로 해소되지 않은 경우."""


def auth_headers(token: str | None, api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def next_run(now: datetime, *, weekday: int, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    if days_ahead == 0 and candidate <= now:
        days_ahead = 7
    return candidate + timedelta(days=days_ahead)


def run_weekly_crawl_once(cfg: ServiceConfig, client: genai.Client | None) -> dict[str, Any]:
    if not cfg.spring_menus_url:
        raise RuntimeError("SPRING_MENUS_URL is required for weekly crawl forwarding")
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is required for weekly analysis")

    menus = load_menus()
    if not menus:
        raise RuntimeError("크롤링 결과가 비었습니다.")
    entries = iter_menu_entries(menus)
    if not entries:
        raise RuntimeError("분석할 메뉴 셀이 없습니다.")

    analysis_results = analyze_menus_with_gemini(
        client,
        cfg.weekly_menu_model,
        entries,
        batch_size=cfg.weekly_batch_size,
        sleep_between_batches_sec=cfg.weekly_sleep_seconds,
    )
    analysis_df = results_to_dataframe(analysis_results)
    i18n_rows = analysis_df.to_dict(orient="records")
    i18n_summary = summarize_for_locale(client, cfg.weekly_menu_model, i18n_rows, cfg.i18n_locale)

    payload = build_extended_menu_payload(
        menus,
        source="https://www.kumoh.ac.kr",
        analysis_df=analysis_df,
        i18n_summary=i18n_summary,
    )
    res = post_menu_ingest(
        cfg.spring_menus_url,
        payload,
        bearer_token=cfg.spring_api_token,
        api_key=cfg.spring_api_key,
        timeout=60.0,
    )
    if not res.ok:
        body = (res.text or "").strip()
        raise RuntimeError(f"메뉴 전송 실패 HTTP {res.status_code}: {body[:500]}")

    return {
        "status": "ok",
        "restaurants": len(payload.get("data", {}).get("restaurants", [])),
        "analysisRows": len(analysis_df),
        "i18nLocale": cfg.i18n_locale,
    }


def analyze_food_text(client: genai.Client | None, model_name: str, name: str) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prompt = f"""음식 이름: {name}

다음 JSON 객체 하나만 출력:
{{
  "foodNameKo": "음식 이름(한국어)",
  "ingredientsKo": ["주요 재료"],
  "allergensKo": [{{"name": "알레르기 유발 가능 식품", "reason": "근거"}}],
  "spicyLevel": 2
}}
spicyLevel은 매운맛 강도로 정수 0(순함·거의 안 매움)~5(아주 매움)만 사용한다.
"""
    resp = client.models.generate_content(
        model=model_name,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
            response_mime_type="application/json",
        ),
    )
    raw = (getattr(resp, "text", "") or "").strip()
    if not raw:
        raise RuntimeError("모델 응답이 비어 있습니다.")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("모델 응답 JSON이 객체 형태가 아닙니다.")
    parsed["spicyLevel"] = clamp_spicy_level(parsed.get("spicyLevel"))
    return parsed


def identify_food_from_image(
    client: genai.Client | None,
    model_name: str,
    image_bytes: bytes,
    mime_type: str,
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prompt = """이미지의 음식 이름만 식별하세요. JSON 객체 하나만 출력:
{"foodNameKo":"...", "confidence": 0.0~1.0}
"""
    resp = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=512,
            response_mime_type="application/json",
        ),
    )
    raw = (getattr(resp, "text", "") or "").strip()
    if not raw:
        raise RuntimeError("모델 응답이 비어 있습니다.")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("모델 응답 JSON이 객체 형태가 아닙니다.")
    return parsed


def extract_menu_text_from_image(
    client: genai.Client | None,
    model_name: str,
    image_bytes: bytes,
    mime_type: str,
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prompt = """메뉴판 이미지에서 메뉴 텍스트를 OCR 관점으로 읽어주세요.
JSON 객체 하나만 출력:
{
  "rawText": "메뉴판에서 읽은 전체 텍스트",
  "menuNames": ["중복 제거된 메뉴명", "메뉴명2"]
}
규칙:
- menuNames는 실제 음식/메뉴명만 포함
- 가격, 날짜, 번호, 안내문구 제외
- 같은 메뉴 중복 제거
"""
    resp = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
            response_mime_type="application/json",
        ),
    )
    raw = (getattr(resp, "text", "") or "").strip()
    if not raw:
        raise RuntimeError("모델 OCR 응답이 비어 있습니다.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini OCR response: %s", raw)
        raise RuntimeError(f"모델 OCR 응답이 유효한 JSON이 아닙니다: {e}") from e
    if not isinstance(parsed, dict):
        raise RuntimeError("모델 OCR 응답 JSON이 객체 형태가 아닙니다.")

    raw_text = parsed.get("rawText")
    if not isinstance(raw_text, str):
        raw_text = ""
    menu_names_raw = parsed.get("menuNames")
    if not isinstance(menu_names_raw, list):
        menu_names_raw = []
    menu_names: list[str] = []
    dedup: set[str] = set()
    for entry in menu_names_raw:
        if not isinstance(entry, str):
            continue
        normalized = entry.strip()
        if not normalized or normalized in dedup:
            continue
        dedup.add(normalized)
        menu_names.append(normalized)
    return {"rawText": raw_text.strip(), "menuNames": menu_names}


def post_json(*, url: str, payload: dict[str, Any], token: str | None, api_key: str | None) -> requests.Response:
    return requests.post(
        url,
        json=payload,
        headers=auth_headers(token, api_key),
        timeout=60.0,
    )


def v1_success(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "data": data}


def v1_error(code: str, msg: str, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "code": code, "msg": msg},
    )


def validate_accept_language(lang: str | None) -> None:
    if not lang:
        return
    first = lang.split(",", 1)[0].strip()
    if not first:
        return
    normalized = first.split(";", 1)[0].strip()
    lowered = normalized.lower()
    if normalized in ALLOWED_ACCEPT_LANGUAGES:
        return
    if lowered.startswith("zh-cn"):
        return
    base_lang = lowered.split("-", 1)[0]
    if base_lang in {"ko", "en", "vi", "ja"}:
        return
    raise ValueError(
        f"지원하지 않는 Accept-Language: {normalized}. "
        "허용: ko, en, zh-CN, vi, ja"
    )


def infer_meal_type(column_name: str) -> str:
    s = column_name.upper()
    if "조식" in column_name or "BREAKFAST" in s:
        return "BREAKFAST"
    if "석식" in column_name or "DINNER" in s:
        return "DINNER"
    return "LUNCH"


_TIME_RANGE_RE = re.compile(r"^\d{1,2}:\d{2}\s*[~\-]\s*\d{1,2}:\d{2}$")
_META_BRACKET_RE = re.compile(r"^\[.*\]$")


def _is_menu_noise(line: str) -> bool:
    """시간 범위, 대괄호 메타정보, 별표 안내문 등 메뉴명이 아닌 항목 판별."""
    if _TIME_RANGE_RE.match(line):
        return True
    if _META_BRACKET_RE.match(line):
        return True
    if line.startswith("*"):
        return True
    return False


_KNOWN_CORNERS = frozenset({"조식", "중식", "석식", "일품요리"})

# 분식당 HTML에 '라면류'·'돈가스류'로만 올라오는 경우 개별 메뉴명으로 펼칩니다.
_BUNSIK_RAMEN_MENUS = ("떡만두라면", "얼큰라면", "치즈라면", "라면", "공깃밥")
_BUNSIK_PORK_CUTLET_MENUS = ("왕돈가스", "고구마돈가스", "치즈돈가스")


def _expand_bunsik_category_tokens(menu_items: list[str]) -> list[str]:
    expanded: list[str] = []
    for item in menu_items:
        s = item.strip()
        if s == "라면류":
            expanded.extend(_BUNSIK_RAMEN_MENUS)
        elif s == "돈가스류":
            expanded.extend(_BUNSIK_PORK_CUTLET_MENUS)
        else:
            expanded.append(item)
    return expanded


def parse_menu_cell(cell_text: str, fallback_corner: str) -> tuple[str, str, list[str]]:
    """셀 텍스트를 파싱하여 (cornerName, mealType, [menuName, ...])을 반환합니다.

    구분자(|||)를 기준으로 항목을 분리하며,
    필터링 후 유효 항목이 하나만 남고 그것이 알려진 코너명이 아닌 경우
    메뉴명으로 취급합니다.
    """
    fallback_corner = normalize_kumoh_cafeteria_name(fallback_corner)
    has_delimiters = MENU_ITEM_DELIM in cell_text
    items = [s.strip() for s in cell_text.split(MENU_ITEM_DELIM) if s.strip()]

    corner_name = ""
    menu_items: list[str] = []

    for item in items:
        if not item or item.lower() == "nan":
            continue
        if "운영 없음" in item:
            continue
        if _is_menu_noise(item):
            continue
        if not corner_name:
            corner_name = item
            continue
        menu_items.append(item)

    if not menu_items and corner_name:
        if not has_delimiters or corner_name not in _KNOWN_CORNERS:
            menu_items = [corner_name]
            corner_name = fallback_corner

    if not corner_name:
        corner_name = fallback_corner

    meal_type = infer_meal_type(corner_name)
    return corner_name, meal_type, menu_items


def sanitize_url_for_log(source_url: str) -> str:
    parsed = urlparse(source_url)
    host = parsed.hostname or ""
    path = parsed.path or "/"
    return f"{parsed.scheme}://{host}{path}"


def extract_date_from_column(column_name: str, start: date, end: date) -> date | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})", column_name)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    candidate_years = [start.year]
    if end.year != start.year:
        candidate_years.append(end.year)

    for year in candidate_years:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            return candidate
    return None


def build_daily_meals(*, cafeteria_name: str, table: Any, start: date, end: date) -> list[dict[str, Any]]:
    cafeteria_name = normalize_kumoh_cafeteria_name(cafeteria_name)
    meals: list[dict[str, Any]] = []
    for column in table.columns:
        meal_date = extract_date_from_column(str(column), start, end)
        if meal_date is None or not (start <= meal_date <= end):
            continue

        meals_by_type: dict[str, list[dict[str, Any]]] = {}

        for _, row in table.iterrows():
            raw = row[column]
            if raw is None:
                continue
            cell_text = str(raw).strip()
            if not cell_text or cell_text.lower() == "nan":
                continue

            corner_name, meal_type, menu_items = parse_menu_cell(cell_text, cafeteria_name)
            if not menu_items:
                continue
            if cafeteria_name == "분식당":
                menu_items = _expand_bunsik_category_tokens(menu_items)
                if not menu_items:
                    continue

            if meal_type not in meals_by_type:
                meals_by_type[meal_type] = []
            for item in menu_items:
                meals_by_type[meal_type].append(
                    {"cornerName": corner_name, "menuName": item}
                )

        for meal_type, menu_list in meals_by_type.items():
            for i, m in enumerate(menu_list, 1):
                m["displayOrder"] = i
            meals.append(
                {
                    "mealDate": meal_date.isoformat(),
                    "mealType": meal_type,
                    "menus": menu_list,
                }
            )

    meals.sort(
        key=lambda item: (
            item["mealDate"],
            MEAL_TYPE_ORDER.get(str(item["mealType"]), 99),
        )
    )
    return meals


def load_menu_table_for_source(*, cafeteria_name: str, source_url: str) -> pd.DataFrame:
    cafeteria_name = normalize_kumoh_cafeteria_name(cafeteria_name)
    _validate_source_url(source_url)
    source_fetch_error: BaseException | None = None

    try:
        response = requests.get(source_url, timeout=15, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise requests.exceptions.RequestException("redirect is not allowed for source_url")
        response.raise_for_status()
        response.encoding = "utf-8"
        table = parse_table_from_html(response.text)
        if table is not None:
            return table
    except (
        requests.exceptions.RequestException,
        ParserError,
        ValueError,
        UnicodeError,
        OSError,
    ) as e:
        source_fetch_error = e
        logger.warning(
            "sourceUrl fetch/parse failed (source=%s): %s",
            sanitize_url_for_log(source_url),
            e,
            exc_info=True,
        )

    fallback_menus = load_menus()
    table = fallback_menus.get(cafeteria_name)
    if table is None:
        if source_fetch_error is not None:
            raise CrawlSourceUpstreamError(
                "sourceUrl fetch/parse failed and fallback cafeteria data was unavailable."
            ) from source_fetch_error
        raise RuntimeError(
            "sourceUrl에서 식단표 파싱에 실패했고, 등록된 식당명 기반 폴백도 실패했습니다."
        )
    return table


def _validate_source_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme.lower() != "https":
        raise RuntimeError("sourceUrl은 https만 허용됩니다.")
    hostname = parsed.hostname
    if not hostname:
        raise RuntimeError("sourceUrl hostname이 비어 있습니다.")
    raw_allowlist = os.environ.get("CRAWL_SOURCE_ALLOWLIST", "").strip()
    if raw_allowlist:
        allowlist = {host.strip().lower() for host in raw_allowlist.split(",") if host.strip()}
    else:
        allowlist = set(DEFAULT_SOURCE_ALLOWLIST)
    normalized_host = hostname.lower()
    if normalized_host not in allowlist:
        raise RuntimeError(f"허용되지 않은 sourceUrl host입니다: {hostname}")
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as e:
        raise RuntimeError(f"sourceUrl DNS 조회 실패: {e}") from e
    for info in infos:
        ip_text = info[4][0]
        ip_obj = ip_address(ip_text)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise RuntimeError("sourceUrl이 사설/내부/예약 IP로 해석되어 차단되었습니다.")


def map_ingredient_code(token: str) -> str | None:
    normalized = token.strip()
    if not normalized:
        return None
    direct = CANONICAL_TO_INGREDIENT_CODE.get(normalized)
    if direct:
        return direct
    normalized_upper = normalized.upper().replace("-", "_").replace(" ", "_")
    if normalized_upper in ALLERGY_API_CODES:
        return normalized_upper

    lowered = normalized.lower()
    by_keyword = ALLERGY_KEYWORD_TO_API_CODE.get(lowered)
    if by_keyword:
        return by_keyword
    for keyword, code in ALLERGY_KEYWORD_TO_API_CODE.items():
        if not keyword:
            continue
        if keyword.isascii():
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return code
            continue
        if keyword in normalized:
            return code
    alias_key = normalized.lower() if normalized.isascii() else normalized
    canonical = ALIAS_TO_CANONICAL.get(normalized) or ALIAS_TO_CANONICAL.get(alias_key)
    if canonical:
        return CANONICAL_TO_INGREDIENT_CODE.get(canonical)
    return None


def translate_text_with_gemini(
    client: genai.Client | None,
    model_name: str,
    source_lang: str,
    target_lang: str,
    text: str,
) -> str:
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prompt = f"""Translate text from {source_lang} to {target_lang}.
Return one JSON object only:
{{
  "translatedText": "..."
}}
Input text:
{text}
"""
    resp = client.models.generate_content(
        model=model_name,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=1024,
            response_mime_type="application/json",
        ),
    )
    raw = (getattr(resp, "text", "") or "").strip()
    if not raw:
        raise RuntimeError("모델 번역 응답이 비어 있습니다.")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("모델 번역 응답 JSON이 객체 형태가 아닙니다.")
    translated = parsed.get("translatedText")
    if not isinstance(translated, str) or not translated.strip():
        raise RuntimeError("모델 번역 응답 형식이 올바르지 않습니다.")
    return translated.strip()


__all__ = [
    "CrawlSourceUpstreamError",
    "auth_headers",
    "analyze_food_text",
    "build_daily_meals",
    "extract_menu_text_from_image",
    "extract_date_from_column",
    "identify_food_from_image",
    "infer_meal_type",
    "load_menu_table_for_source",
    "map_ingredient_code",
    "next_run",
    "parse_menu_cell",
    "post_json",
    "run_weekly_crawl_once",
    "sanitize_url_for_log",
    "translate_text_with_gemini",
    "validate_accept_language",
    "v1_error",
    "v1_success",
]
