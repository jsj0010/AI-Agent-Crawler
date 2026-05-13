"""금오공대 급식 크롤링/전송 도메인 모듈."""

from app.domain.crawler.kumoh_menu import URLS, fetch_html, load_menus, normalize_kumoh_cafeteria_name

__all__ = ["URLS", "fetch_html", "load_menus", "normalize_kumoh_cafeteria_name"]
