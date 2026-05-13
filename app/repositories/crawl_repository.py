"""크롤링/메뉴 데이터 접근 Repository."""

from __future__ import annotations

from datetime import date
from typing import Any

from google import genai

from app.domain.crawler.kumoh_menu import normalize_kumoh_cafeteria_name
from app.domain.entities import MenuCrawlQuery
from app.common.service_ops import build_daily_meals, load_menu_table_for_source, run_weekly_crawl_once


class CrawlRepository:
    """크롤링/메뉴 데이터 접근 Repository."""

    def load_menu_table_for_source(self, query: MenuCrawlQuery):
        return load_menu_table_for_source(
            cafeteria_name=normalize_kumoh_cafeteria_name(query.cafeteria_name),
            source_url=query.source_url,
        )

    def build_daily_meals(
        self,
        *,
        cafeteria_name: str,
        table: Any,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        return build_daily_meals(cafeteria_name=cafeteria_name, table=table, start=start, end=end)

    def run_weekly_crawl_once(self, cfg, client: genai.Client | None) -> dict[str, Any]:
        return run_weekly_crawl_once(cfg, client)
