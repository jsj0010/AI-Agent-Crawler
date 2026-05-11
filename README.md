# AI-Agent-Crawler

Spring Boot 내부 호출 전용 Python API 서버입니다. 현재는 아래 API를 제공합니다.

- `POST /api/v1/python/meals/crawl`
- `POST /api/v1/python/menus/analyze`
- `POST /api/v1/python/menus/analyze-image`
- `POST /api/v1/python/menus/translate`

---

## 요구 사항

- Python 3.10+
- `pip install -r requirements.txt`
- AI 분석/번역 사용 시 `GEMINI_API_KEY` 필요

---

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

문서 확인:

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 공통 규칙

- Base URL: `/api/v1`
- 헤더:
  - `Content-Type: application/json`
  - `Accept-Language: ko | en | zh-CN | vi | ja` (`en-US`, `ko-KR` 같은 locale 변형도 허용)
- 성공 응답:

```json
{
  "success": true,
  "data": {}
}
```

- 실패 응답:

```json
{
  "success": false,
  "code": "COM_002",
  "msg": "요청 데이터 변환 과정에서 오류가 발생했습니다."
}
```

---

## API 목록

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/v1/python/meals/crawl` | 주간 식단 크롤링 |
| `POST` | `/api/v1/python/menus/analyze` | 메뉴 재료/알레르기 코드 분석 |
| `POST` | `/api/v1/python/menus/analyze-image` | 이미지 기반 메뉴 재료/알레르기 코드 분석 |
| `POST` | `/api/v1/python/menus/translate` | 메뉴명 번역 |

---

## 1) 식단 조회 API

### `POST /api/v1/python/meals/crawl`

Java 서버 스케줄러가 호출하여 일주일치 식단을 수집할 때 사용합니다.

### 요청 DTO

```java
public record PythonMealCrawlRequest(
        String schoolName,
        String cafeteriaName,
        String sourceUrl,
        LocalDate startDate,
        LocalDate endDate
) { }
```

요청 예시:

```json
{
  "schoolName": "금오공과대학교",
  "cafeteriaName": "학생식당",
  "sourceUrl": "https://example.com/menu",
  "startDate": "2026-04-15",
  "endDate": "2026-04-21"
}
```

### 응답 DTO

```java
public record PythonMealCrawlResponse(
        String schoolName,
        String cafeteriaName,
        String sourceUrl,
        LocalDate startDate,
        LocalDate endDate,
        List<PythonDailyMealDto> meals
) { }

public record PythonDailyMealDto(
        LocalDate mealDate,
        String mealType,
        List<PythonCrawledMenuDto> menus
) { }

public record PythonCrawledMenuDto(
        String cornerName,
        Integer displayOrder,
        String menuName
) { }
```

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "schoolName": "금오공과대학교",
    "cafeteriaName": "학생식당",
    "sourceUrl": "https://example.com/menu",
    "startDate": "2026-04-15",
    "endDate": "2026-04-21",
    "meals": [
      {
        "mealDate": "2026-04-15",
        "mealType": "LUNCH",
        "menus": [
          { "cornerName": "한식", "displayOrder": 1, "menuName": "김치찌개" },
          { "cornerName": "한식", "displayOrder": 2, "menuName": "계란말이" }
        ]
      }
    ]
  }
}
```

실패 응답 예시:

```json
{ "success": false, "code": "PYM_400", "msg": "요청 식단 조회 조건이 유효하지 않거나 데이터가 없습니다." }
```

```json
{ "success": false, "code": "PYM_502", "msg": "외부 크롤링 소스 조회에 실패했습니다. 잠시 후 다시 시도해주세요." }
```

---

## 2) 메뉴 분석 API

### `POST /api/v1/python/menus/analyze`

식단 저장 후 분석이 없는 메뉴만 Java 서버가 요청합니다.

### 요청 DTO

```java
public record PythonMenuAnalysisRequest(
        List<PythonMenuAnalysisTargetDto> menus
) { }

public record PythonMenuAnalysisTargetDto(
        Long menuId,
        String menuName
) { }
```

요청 예시:

```json
{
  "menus": [
    { "menuId": 101, "menuName": "김치찌개" },
    { "menuId": 102, "menuName": "돈까스" }
  ]
}
```

### 응답 DTO

```java
public record PythonMenuAnalysisResponse(
        List<PythonMenuAnalysisResultDto> results
) { }

public record PythonMenuAnalysisResultDto(
        Long menuId,
        String menuName,
        String status,
        String reason,
        String modelName,
        String modelVersion,
        LocalDateTime analyzedAt,
        List<PythonMenuIngredientResultDto> ingredients
) { }

public record PythonMenuIngredientResultDto(
        String ingredientCode,
        BigDecimal confidence
) { }
```

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 101,
        "menuName": "김치찌개",
        "status": "COMPLETED",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "2.5",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.97 },
          { "ingredientCode": "SHRIMP", "confidence": 0.81 },
          { "ingredientCode": "SOYBEAN", "confidence": 0.88 }
        ]
      }
    ]
  }
}
```

실패 응답 예시:

```json
{ "success": false, "code": "AI_001", "msg": "GEMINI_API_KEY is not set" }
```

---

## 3) 메뉴 번역 API

### `POST /api/v1/python/menus/translate`

번역이 없는 메뉴만 Java 서버가 요청합니다.

### 요청 DTO

```java
public record PythonMenuTranslationRequest(
        List<PythonMenuTranslationTargetDto> menus,
        List<String> targetLanguages
) { }

public record PythonMenuTranslationTargetDto(
        Long menuId,
        String menuName
) { }
```

요청 예시:

```json
{
  "menus": [
    { "menuId": 101, "menuName": "김치찌개" },
    { "menuId": 102, "menuName": "돈까스" }
  ],
  "targetLanguages": ["en"]
}
```

### 응답 DTO

```java
public record PythonMenuTranslationResponse(
        List<PythonMenuTranslationResultDto> results
) { }

public record PythonMenuTranslationResultDto(
        Long menuId,
        String sourceName,
        List<PythonTranslatedMenuNameDto> translations
) { }

public record PythonTranslatedMenuNameDto(
        String langCode,
        String translatedName
) { }
```

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 101,
        "sourceName": "김치찌개",
        "translations": [
          { "langCode": "en", "translatedName": "Kimchi Stew" }
        ]
      },
      {
        "menuId": 102,
        "sourceName": "돈까스",
        "translations": [
          { "langCode": "en", "translatedName": "Pork Cutlet" }
        ]
      }
    ]
  }
}
```

실패 응답 예시:

```json
{ "success": false, "code": "AI_001", "msg": "GEMINI_API_KEY is not set" }
```

---

## 4) 이미지 메뉴 분석 API

### `POST /api/v1/python/menus/analyze-image`

추후 확장을 위해 추가한 API입니다. 이미지 입력이지만, 응답은 텍스트 분석과 동일하게 `results` 배열 DTO를 사용합니다.

요청 형식:

- `multipart/form-data`
- `image`: 이미지 파일 (필수)
- `menuId`: 메뉴 매핑용 ID (필수)
- `menuName`: 메뉴명 (필수)

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 101,
        "menuName": "김치찌개",
        "status": "COMPLETED",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "2.5",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.92 },
          { "ingredientCode": "SOYBEAN", "confidence": 0.88 }
        ]
      }
    ]
  }
}
```

실패 응답 예시:

```json
{ "success": false, "code": "COM_001", "msg": "이미지 파일이 비어 있습니다." }
```

```json
{ "success": false, "code": "AI_001", "msg": "GEMINI_API_KEY is not set" }
```

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | 없음 | 메뉴 분석/번역에 필요 |
| `GEMINI_MODEL` | `gemini-2.5-flash` | AI 모델명 |
| `AI_MAX_CONCURRENT_TASKS` | `4` | 분석/번역 동시성 |
| `SERVICE_TIMEZONE` | `Asia/Seoul` | 분석 시각 타임존 |
| `CRAWL_SOURCE_ALLOWLIST` | 없음(제한 없음) | 크롤 허용 호스트 화이트리스트. 설정 시 해당 호스트만 `sourceUrl` 허용 (SSRF 방어) |

예시:

```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
AI_MAX_CONCURRENT_TASKS=4
SERVICE_TIMEZONE=Asia/Seoul
CRAWL_SOURCE_ALLOWLIST=www.kumoh.ac.kr,kumoh.ac.kr
```

---

## 테스트

```bash
python3 -m pytest -q tests/live
python3 -m pytest -q tests/integration
```
