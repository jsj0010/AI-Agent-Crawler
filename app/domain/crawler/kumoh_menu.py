"""금오공대 식당 급식표 HTML에서 메뉴 테이블을 가져옵니다."""

from __future__ import annotations

import logging
import re
from io import StringIO

import pandas as pd
import requests
from pandas.errors import ParserError

logger = logging.getLogger(__name__)

URLS = {
    "학생식당": "https://www.kumoh.ac.kr/ko/restaurant01.do",
    "교직원식당": "https://www.kumoh.ac.kr/ko/restaurant02.do",
    "분식당": "https://www.kumoh.ac.kr/ko/restaurant04.do",
}

MENU_ITEM_DELIM = "|||"
_LI_CLOSE_RE = re.compile(r"</li\s*>", re.IGNORECASE)
_P_CLOSE_RE = re.compile(r"</p\s*>", re.IGNORECASE)


def preprocess_menu_html(html: str) -> str:
    """<li>, <p> 태그 뒤에 구분자를 삽입하여 pd.read_html() 이후에도 항목 경계를 보존합니다."""
    html = _P_CLOSE_RE.sub(f"</p>{MENU_ITEM_DELIM}", html)
    html = _LI_CLOSE_RE.sub(f"</li>{MENU_ITEM_DELIM}", html)
    return html


def parse_table_from_html(html: str) -> pd.DataFrame | None:
    """HTML을 전처리한 뒤 첫 번째 테이블을 DataFrame으로 반환합니다."""
    preprocessed = preprocess_menu_html(html)
    try:
        tables = pd.read_html(StringIO(preprocessed))
    except (ValueError, ParserError):
        return None
    if not tables:
        return None
    df = tables[0].copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.replace(r"\s+", " ", regex=True)
    return df


def fetch_html(url: str) -> str:
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    res.encoding = "utf-8"
    return res.text


def load_menus() -> dict[str, pd.DataFrame]:
    menus: dict[str, pd.DataFrame] = {}
    for name, url in URLS.items():
        try:
            html = fetch_html(url)
            df = parse_table_from_html(html)
            if df is None:
                continue
            menus[name] = df
        except (
            requests.exceptions.RequestException,
            ParserError,
            ValueError,
            UnicodeError,
            OSError,
        ) as e:
            logger.warning("[%s] 메뉴 로드 실패: %s", name, type(e).__name__)
            continue
    return menus
