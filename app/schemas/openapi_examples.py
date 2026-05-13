"""Swagger/OpenAPI용 요청·응답 예시 상수 (README와 동기화 권장)."""

from __future__ import annotations

# --- POST /api/v1/python/meals/crawl ---
MEAL_CRAWL_REQUEST_OPENAPI_EXAMPLES: dict = {
    "기본": {
        "summary": "금오공대 일품식당 주간 조회",
        "description": "Accept-Language: ko 권장",
        "value": {
            "schoolName": "금오공과대학교",
            "cafeteriaName": "일품식당",
            "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
            "startDate": "2026-04-21",
            "endDate": "2026-04-27",
        },
    }
}

MEAL_CRAWL_SUCCESS_EXAMPLE: dict = {
    "success": True,
    "data": {
        "schoolName": "금오공과대학교",
        "cafeteriaName": "일품식당",
        "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
        "startDate": "2026-04-21",
        "endDate": "2026-04-27",
        "meals": [
            {
                "mealDate": "2026-04-21",
                "mealType": "LUNCH",
                "menus": [
                    {"cornerName": "일품요리", "displayOrder": 1, "menuName": "김치찌개"},
                    {"cornerName": "일품요리", "displayOrder": 2, "menuName": "된장찌개"},
                ],
            }
        ],
    },
}

MEAL_CRAWL_ERROR_UPSTREAM_EXAMPLE: dict = {
    "success": False,
    "code": "PYM_502",
    "msg": "외부 크롤링 소스 조회에 실패했습니다. 잠시 후 다시 시도해주세요.",
}

MEAL_CRAWL_ERROR_BAD_CONDITION_EXAMPLE: dict = {
    "success": False,
    "code": "PYM_400",
    "msg": "요청 식단 조회 조건이 유효하지 않거나 데이터가 없습니다.",
}

# 식단 크롤 등에서 처리 중 예기치 않은 오류 시(문서용 예시; README PYM_500과 정합)
V1_INTERNAL_SERVER_ERROR_EXAMPLE: dict = {
    "success": False,
    "code": "PYM_500",
    "msg": "식단 조회 처리 중 서버 오류가 발생했습니다.",
}

# --- POST /api/v1/python/menus/analyze ---
MENU_ANALYZE_REQUEST_OPENAPI_EXAMPLES: dict = {
    "기본": {
        "summary": "메뉴 1건 분석",
        "value": {"menus": [{"menuId": 101, "menuName": "김치찌개"}]},
    }
}

MENU_ANALYZE_SUCCESS_EXAMPLE: dict = {
    "success": True,
    "data": {
        "results": [
            {
                "menuId": 101,
                "menuName": "김치찌개",
                "status": "COMPLETED",
                "reason": None,
                "modelName": "gemini",
                "modelVersion": "gemini-2.5-flash",
                "analyzedAt": "2026-04-27T12:00:00",
                "ingredients": [
                    {"ingredientCode": "SOYBEAN", "confidence": 0.88},
                    {"ingredientCode": "WHEAT", "confidence": 0.81},
                ],
            }
        ]
    },
}

AI_KEY_MISSING_EXAMPLE: dict = {
    "success": False,
    "code": "AI_001",
    "msg": "GEMINI_API_KEY is not set",
}

# --- POST /api/v1/python/menus/translate ---
MENU_TRANSLATE_REQUEST_OPENAPI_EXAMPLES: dict = {
    "기본": {
        "summary": "영·일 번역",
        "value": {
            "menus": [{"menuId": 101, "menuName": "김치찌개"}],
            "targetLanguages": ["en", "ja"],
        },
    }
}

MENU_TRANSLATE_SUCCESS_EXAMPLE: dict = {
    "success": True,
    "data": {
        "results": [
            {
                "menuId": 101,
                "sourceName": "김치찌개",
                "translations": [
                    {"langCode": "en", "translatedName": "Kimchi stew"},
                    {"langCode": "ja", "translatedName": "キムチチゲ"},
                ],
                "translationErrors": [],
            }
        ]
    },
}

# --- POST /api/v1/translations ---
FREE_TRANSLATION_REQUEST_OPENAPI_EXAMPLES: dict = {
    "기본": {
        "summary": "한→영 문장 번역",
        "value": {
            "sourceLang": "ko",
            "targetLang": "en",
            "text": "이 음식에 밀가루가 들어가나요?",
        },
    }
}

FREE_TRANSLATION_SUCCESS_EXAMPLE: dict = {
    "success": True,
    "data": {
        "sourceLang": "ko",
        "targetLang": "en",
        "text": "이 음식에 밀가루가 들어가나요?",
        "translatedText": "Does this dish contain flour?",
    },
}

# --- multipart (문서용 설명; Swagger는 폼 필드 설명으로 표시) ---
MENU_BOARD_ANALYZE_RESPONSE_EXAMPLE: dict = {
    "success": True,
    "data": {
        "requestId": "req-001",
        "recognizedMenus": [{"menuName": "김치찌개", "confidence": 0.82}],
    },
}

FOOD_IMAGE_ANALYZE_RESPONSE_EXAMPLE: dict = {
    "success": True,
    "data": {
        "requestId": "req-002",
        "foodName": "김치찌개",
        "ingredients": [
            {"ingredientCode": "SOYBEAN", "confidence": 0.9},
            {"ingredientCode": "WHEAT", "confidence": 0.75},
        ],
        "notes": "추정 결과이며 실제와 다를 수 있습니다.",
    },
}

VALIDATION_ERROR_EXAMPLE: dict = {
    "success": False,
    "code": "COM_002",
    "msg": "요청 데이터 변환 과정에서 오류가 발생했습니다.",
}

BAD_REQUEST_COM001_EXAMPLE: dict = {
    "success": False,
    "code": "COM_001",
    "msg": "이미지 파일이 비어 있습니다.",
}

PAYLOAD_TOO_LARGE_COM001_EXAMPLE: dict = {
    "success": False,
    "code": "COM_001",
    "msg": "이미지 파일이 너무 큽니다 (최대 10MB).",
}
