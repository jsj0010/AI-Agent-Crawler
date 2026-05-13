# Live Service 구조 안내

Spring Boot에서 Python 서버를 호출하기 쉽게 계층을 분리했습니다.

## 계층 구성
- **Controller**: `routers.py`
- **Service**: `services.py` (`LiveService`)
- **Repository**: `repositories.py`
- **DTO**: `api_models.py` (요청/응답 스키마)
- **Entity**: `entities.py` (도메인 질의/전달 객체)

## 1) Controller 계층 (`routers.py`)
- HTTP 요청/응답 처리
- 입력 검증 (`pydantic`, 파일 크기/형식 확인)
- 에러 코드를 API 응답 포맷으로 변환

## 2) Service 계층 (`services.py`)
- 비즈니스 로직 진입점 클래스: `LiveService`
- 라우터는 `LiveService` 메서드만 호출
- 내부적으로 Repository를 통해 외부/도메인 접근

## 3) Repository 계층 (`repositories.py`)
- 크롤링/AI/Spring API 연동 책임 분리
- `service_ops.py`의 순수 함수를 래핑해 인프라 접근 캡슐화

## 4) DTO 계층 (`api_models.py`)
- FastAPI + pydantic 기반 요청 DTO

## 5) Entity 계층 (`entities.py`)
- 서비스 내부에서 쓰는 도메인 객체

## 호출 흐름
1. Spring Boot -> FastAPI endpoint 호출
2. Controller가 요청 검증
3. Controller가 `LiveService` 호출
4. Service가 Repository를 통해 처리
5. Controller가 통일된 JSON 응답 반환

## 주요 메서드 (`LiveService`)
- `run_weekly_crawl_once()`
- `load_menu_table_for_source(cafeteria_name, source_url)`
- `build_daily_meals(...)`
- `analyze_food_text(food_name)`
- `identify_food_from_image(image_bytes, mime_type)`
- `translate_text(source_lang, target_lang, text)`
- `forward_to_spring(url, payload)`

## Spring 연동 엔드포인트 예시 (JSON)

Spring Boot에서 Python 서버를 호출할 때 바로 참고할 수 있는 최소 예시입니다.

### 1) 식단 크롤링 요청
- `POST /api/v1/python/meals/crawl`

요청:
```json
{
  "schoolName": "KUMOH",
  "cafeteriaName": "일품식당",
  "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
  "startDate": "2026-03-23",
  "endDate": "2026-03-27"
}
```

응답:
```json
{
  "success": true,
  "data": {
    "schoolName": "KUMOH",
    "cafeteriaName": "일품식당",
    "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
    "startDate": "2026-03-23",
    "endDate": "2026-03-27",
    "meals": [
      {
        "mealDate": "2026-03-23",
        "mealType": "LUNCH",
        "menus": [
          {
            "cornerName": "일품요리",
            "displayOrder": 1,
            "menuName": "쌀밥 닭곰탕 ..."
          }
        ]
      }
    ]
  }
}
```

### 2) 메뉴 재료/알레르기 분석
- `POST /api/v1/python/menus/analyze`

요청:
```json
{
  "menus": [
    { "menuId": 101, "menuName": "참치김치찌개" },
    { "menuId": 102, "menuName": "한입돈까스" }
  ]
}
```

응답:
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 101,
        "menuName": "참치김치찌개",
        "status": "COMPLETED",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "gemini-2.5-flash-lite",
        "analyzedAt": "2026-04-24T10:00:00+09:00",
        "ingredients": [
          { "ingredientCode": "SOYBEAN", "confidence": 0.88 }
        ]
      }
    ]
  }
}
```

### 3) 메뉴 다국어 번역
- `POST /api/v1/python/menus/translate`

요청:
```json
{
  "menus": [
    { "menuId": 201, "menuName": "닭곰탕" }
  ],
  "targetLanguages": ["en", "ja"]
}
```

응답:
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 201,
        "sourceName": "닭곰탕",
        "translations": [
          { "langCode": "en", "translatedName": "Chicken soup" },
          { "langCode": "ja", "translatedName": "タッコムタン" }
        ],
        "translationErrors": []
      }
    ]
  }
}
```

### 4) 음식 사진 분석 (멀티파트 업로드)
- `POST /api/v1/ai/food-images/analyze`
- Content-Type: `multipart/form-data`
- form fields:
  - `image`: 바이너리 파일
  - `requestId`: optional

응답:
```json
{
  "success": true,
  "data": {
    "requestId": "req-123",
    "foodName": "비빔밥",
    "ingredients": [
      { "ingredientCode": "EGG", "confidence": 0.74 },
      { "ingredientCode": "SOYBEAN", "confidence": 0.68 }
    ],
    "notes": "유사한 덮밥류와 혼동 가능"
  }
}
```

### 공통 에러 응답
```json
{
  "success": false,
  "code": "COM_001",
  "msg": "요청 메시지 오류 내용"
}
```

