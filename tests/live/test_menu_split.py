"""개별 메뉴 분리 로직 단위 테스트.

HTML 전처리 → DataFrame → build_daily_meals() 파이프라인에서
셀 하나가 개별 menuName 여러 개로 분리되는지 검증합니다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.crawler.kumoh_menu import MENU_ITEM_DELIM, preprocess_menu_html
from app.services.ops import build_daily_meals, parse_menu_cell


class TestPreprocessMenuHtml:
    def test_inserts_delimiter_after_li_and_p(self):
        html = (
            "<td><p>일품요리</p>"
            '<ul class="s-dot">'
            "<li>11:00~14:00</li>"
            "<li>스팸짜글이</li>"
            "</ul></td>"
        )
        result = preprocess_menu_html(html)
        assert result.count(MENU_ITEM_DELIM) == 3  # </p>, 2x </li>

    def test_case_insensitive(self):
        html = "<P>코너</P><LI>메뉴</LI>"
        result = preprocess_menu_html(html)
        assert result.count(MENU_ITEM_DELIM) == 2


class TestParseMenuCell:
    def test_splits_lunch_menus(self):
        cell = f"일품요리{MENU_ITEM_DELIM} 11:00~14:00{MENU_ITEM_DELIM} 16:00~18:30{MENU_ITEM_DELIM} 스팸짜글이{MENU_ITEM_DELIM} 매콤치밥{MENU_ITEM_DELIM} 하이라이스{MENU_ITEM_DELIM}"
        corner, meal_type, items = parse_menu_cell(cell, "일품식당")
        assert corner == "일품요리"
        assert meal_type == "LUNCH"
        assert items == ["스팸짜글이", "매콤치밥", "하이라이스"]

    def test_splits_breakfast_menus(self):
        cell = f"조식{MENU_ITEM_DELIM} [천원의 아침밥]{MENU_ITEM_DELIM} *재학생만 해당{MENU_ITEM_DELIM} 08:20~10:00{MENU_ITEM_DELIM} 도시락A{MENU_ITEM_DELIM} 김밥B{MENU_ITEM_DELIM}"
        corner, meal_type, items = parse_menu_cell(cell, "일품식당")
        assert corner == "조식"
        assert meal_type == "BREAKFAST"
        assert items == ["도시락A", "김밥B"]

    def test_splits_faculty_lunch(self):
        cell = f"중식{MENU_ITEM_DELIM} [정식: 6000원]{MENU_ITEM_DELIM} 11:30~13:30{MENU_ITEM_DELIM} 잡곡밥{MENU_ITEM_DELIM} 된장국{MENU_ITEM_DELIM} 배추김치{MENU_ITEM_DELIM}"
        corner, meal_type, items = parse_menu_cell(cell, "정찬식당")
        assert corner == "중식"
        assert meal_type == "LUNCH"
        assert items == ["잡곡밥", "된장국", "배추김치"]

    def test_operation_closed_returns_empty(self):
        cell = f"일품요리{MENU_ITEM_DELIM} 식당 운영 없음{MENU_ITEM_DELIM}"
        _corner, _meal_type, items = parse_menu_cell(cell, "일품식당")
        assert items == []

    def test_no_delimiter_fallback(self):
        cell = "김치찌개"
        corner, _meal_type, items = parse_menu_cell(cell, "학생식당")
        assert corner == "일품식당"
        assert items == ["김치찌개"]

    def test_no_delimiter_operation_closed(self):
        cell = "조식 식당 운영 없음"
        _corner, _meal_type, items = parse_menu_cell(cell, "일품식당")
        assert items == []

    def test_dinner_meal_type(self):
        cell = f"석식{MENU_ITEM_DELIM} 17:00~18:30{MENU_ITEM_DELIM} 돈까스{MENU_ITEM_DELIM}"
        corner, meal_type, items = parse_menu_cell(cell, "일품식당")
        assert corner == "석식"
        assert meal_type == "DINNER"
        assert items == ["돈까스"]

    def test_single_menu_with_delimiter_not_lost(self):
        """단일 메뉴만 <li>로 감싸진 경우에도 메뉴가 누락되지 않아야 합니다."""
        cell = f"김치찌개{MENU_ITEM_DELIM}"
        corner, _meal_type, items = parse_menu_cell(cell, "일품식당")
        assert corner == "일품식당"
        assert items == ["김치찌개"]

    def test_known_corner_alone_with_delimiter_returns_empty(self):
        """알려진 코너명만 남은 경우 메뉴 없이 빈 리스트를 반환합니다."""
        cell = f"조식{MENU_ITEM_DELIM}"
        corner, meal_type, items = parse_menu_cell(cell, "일품식당")
        assert corner == "조식"
        assert meal_type == "BREAKFAST"
        assert items == []


class TestBuildDailyMeals:
    @staticmethod
    def _make_df(data: dict[str, list[str]]) -> pd.DataFrame:
        return pd.DataFrame(data)

    def test_splits_into_individual_menus(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "월(05.12)": [
                    f"조식{D} 08:20~10:00{D} 도시락A{D}",
                    f"일품요리{D} 11:00~14:00{D} 김치우동{D} 목살필라프{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="일품식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        assert len(meals) == 2

        breakfast = next(m for m in meals if m["mealType"] == "BREAKFAST")
        assert len(breakfast["menus"]) == 1
        assert breakfast["menus"][0]["menuName"] == "도시락A"
        assert breakfast["menus"][0]["cornerName"] == "조식"

        lunch = next(m for m in meals if m["mealType"] == "LUNCH")
        assert len(lunch["menus"]) == 2
        menu_names = [m["menuName"] for m in lunch["menus"]]
        assert menu_names == ["김치우동", "목살필라프"]

    def test_display_order_sequential(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "월(05.12)": [
                    f"일품요리{D} 11:00~14:00{D} A{D} B{D} C{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="일품식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        orders = [m["displayOrder"] for m in meals[0]["menus"]]
        assert orders == [1, 2, 3]

    def test_operation_closed_skipped(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "토(05.16)": [
                    f"조식{D} 식당 운영 없음{D}",
                    f"일품요리{D} 식당 운영 없음{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="일품식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        assert meals == []

    def test_sorts_by_date_and_meal_type(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "화(05.13)": [
                    f"석식{D} 돈까스{D}",
                    f"조식{D} 토스트{D}",
                ],
                "월(05.12)": [
                    f"일품요리{D} 비빔밥{D}",
                    f"조식{D} 도시락{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="일품식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        keys = [(m["mealDate"], m["mealType"]) for m in meals]
        assert keys == [
            ("2026-05-12", "BREAKFAST"),
            ("2026-05-12", "LUNCH"),
            ("2026-05-13", "BREAKFAST"),
            ("2026-05-13", "DINNER"),
        ]

    def test_faculty_cafeteria_multiple_items(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "월(05.12)": [
                    f"중식{D} [정식: 6000원]{D} 11:30~13:30{D} 잡곡밥{D} 된장국{D} 불고기{D} 배추김치{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="정찬식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        assert len(meals) == 1
        assert meals[0]["mealType"] == "LUNCH"
        names = [m["menuName"] for m in meals[0]["menus"]]
        assert names == ["잡곡밥", "된장국", "불고기", "배추김치"]
        assert all(m["cornerName"] == "중식" for m in meals[0]["menus"])

    def test_bunsik_expands_ramen_and_cutlet_categories(self):
        D = MENU_ITEM_DELIM
        df = self._make_df(
            {
                "월(05.12)": [
                    f"일품요리{D} 11:00~14:00{D} 16:00~18:30{D} 라면류{D} 돈가스류{D}",
                ],
            }
        )
        meals = build_daily_meals(
            cafeteria_name="분식당",
            table=df,
            start=date(2026, 5, 11),
            end=date(2026, 5, 17),
        )
        assert len(meals) == 1
        names = [m["menuName"] for m in meals[0]["menus"]]
        assert names == [
            "떡만두라면",
            "얼큰라면",
            "치즈라면",
            "라면",
            "공깃밥",
            "왕돈가스",
            "고구마돈가스",
            "치즈돈가스",
        ]
