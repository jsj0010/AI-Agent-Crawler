# AI-Agent-Crawler

Spring Boot 내부 호출 전용 Python API 서버입니다. 현재는 아래 API를 제공합니다.

### Wrapped API (`/api/v1/python/...`)

`{success, data}` 형태로 래핑된 응답을 반환합니다.

- `POST /api/v1/python/meals/crawl`
- `POST /api/v1/python/menus/analyze`
- `POST /api/v1/python/menus/ocr`
- `POST /api/v1/python/menus/analyze-from-ocr`
- `POST /api/v1/python/menus/analyze-image`
- `POST /api/v1/python/menus/translate`

헬스(래핑 없음, Base URL 밖): `GET /health`

### Spring Native API (Unwrapped)

Spring WebClient가 직접 파싱할 수 있도록 래핑 없이 결과를 반환합니다.

- `POST /api/v1/crawl/meals`
- `POST /api/v1/menus/analyze`
- `POST /api/v1/translations`

---

## 요구 사항

- Python 3.10+
- `pip install -r requirements.txt`
- AI 분석/번역 사용 시 `GEMINI_API_KEY` 필요

---

## 실행

### 로컬 (직접 실행)

```bash
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 등 필요한 값 설정

# docker compose로 실행
docker compose up -d

# 로그 확인
docker compose logs -f

# 중지
docker compose down
```

빌드만 따로 하려면:

```bash
docker build -t ai-agent-crawler .
docker run -d --env-file .env -p 8000:8000 ai-agent-crawler
```

문서 확인:

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 공통 규칙

- Base URL: `/api/v1`
- 헤더:
  - `Content-Type`: 기본은 `application/json`, 이미지 업로드 API는 `multipart/form-data`
  - `Accept-Language: ko | en | zh-CN | vi | ja` (`en-US`, `ko-KR` 같은 locale 변형도 허용)

### Wrapped 응답 (`/api/v1/python/...`)

```json
{
  "success": true,
  "data": {}
}
```

### Unwrapped 응답 (Spring Native)

래핑 없이 결과를 직접 반환합니다.

```json
{
  "schoolName": "...",
  "cafeteriaName": "...",
  "meals": [...]
}
```

### 실패 응답 (공통)

```json
{
  "success": false,
  "code": "COM_002",
  "msg": "요청 데이터 변환 과정에서 오류가 발생했습니다."
}
```

---

## API 목록

### Wrapped API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/v1/python/meals/crawl` | 주간 식단 크롤링 |
| `POST` | `/api/v1/python/menus/analyze` | 메뉴 재료·알레르기 코드·매운맛(0~5) 분석 |
| `POST` | `/api/v1/python/menus/ocr` | 메뉴판 이미지 OCR 추출 |
| `POST` | `/api/v1/python/menus/analyze-from-ocr` | 메뉴판 OCR 후 연속 분석 |
| `POST` | `/api/v1/python/menus/analyze-image` | 이미지 기반 메뉴 재료/알레르기 코드 분석 |
| `POST` | `/api/v1/python/menus/translate` | 메뉴명 번역 |

### Spring Native API (Unwrapped)

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/v1/crawl/meals` | 식단 크롤링 (래핑 없이 반환) |
| `POST` | `/api/v1/menus/analyze` | 메뉴 AI 분석 (래핑 없이 반환) |
| `POST` | `/api/v1/translations` | 자유 텍스트 번역 |

### 헬스

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 프로세스 헬스(본문 `{"status":"ok"}` 형태, `/api/v1` 밖) |

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
  "cafeteriaName": "일품식당",
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
    "cafeteriaName": "일품식당",
    "sourceUrl": "https://example.com/menu",
    "startDate": "2026-04-15",
    "endDate": "2026-04-21",
    "meals": [
      {
        "mealDate": "2026-04-15",
        "mealType": "BREAKFAST",
        "menus": [
          { "cornerName": "조식", "displayOrder": 1, "menuName": "다찬스페셜정식도시락" }
        ]
      },
      {
        "mealDate": "2026-04-15",
        "mealType": "LUNCH",
        "menus": [
          { "cornerName": "일품요리", "displayOrder": 1, "menuName": "김치우동" },
          { "cornerName": "일품요리", "displayOrder": 2, "menuName": "목살필라프" },
          { "cornerName": "일품요리", "displayOrder": 3, "menuName": "참치마요덮밥" }
        ]
      }
    ]
  }
}
```

> **메뉴 분리 규칙**: HTML `<li>` 태그 기준으로 메뉴를 개별 분리합니다.
> 셀에 포함된 시간 범위(`11:00~14:00`), 메타정보(`[천원의 아침밥]`), 안내문(`*재학생만 해당`) 등은 자동 필터링됩니다.
> `cornerName`은 셀의 첫 번째 항목(조식, 일품요리, 중식 등)에서 추출되며, `mealType`도 이로부터 추론됩니다.

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

식단 저장 후 분석이 없는 메뉴만 Java 서버가 요청합니다. 응답 스키마는 코드 기준 `app/schemas/api_models.py`의 `PythonMenuAnalysisResultDto`와 동일합니다.

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
        List<PythonMenuIngredientResultDto> ingredients,
        List<PythonMenuAllergyResultDto> allergies,
        Integer spicyLevel
) { }

public record PythonMenuIngredientResultDto(
        String ingredientCode,
        BigDecimal confidence
) { }

public record PythonMenuAllergyResultDto(
        String allergyCode,
        BigDecimal confidence
) { }
```

- `status`: 성공 시 `SUCCESS`, 예외 시 `FAILED`.
- `spicyLevel`: 매운맛 **0(순함)~5(아주 매움)** 정수. 모델이 내지 않거나 실패·이미지 분석 등으로 값이 없을 때는 **0**으로 채워집니다.
- `ingredients`: 추정 식재료 코드 목록.
- `allergies`: 알레르기 유발 추정 코드 목록(`allergyCode`). 분석 실패 시 빈 배열.

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 101,
        "menuName": "김치찌개",
        "status": "SUCCESS",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "gemini-2.5-flash",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.97 },
          { "ingredientCode": "SHRIMP", "confidence": 0.81 },
          { "ingredientCode": "SOYBEAN", "confidence": 0.88 }
        ],
        "allergies": [
          { "allergyCode": "SOYBEAN", "confidence": 0.85 }
        ],
        "spicyLevel": 3
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

## 4) 메뉴판 OCR API

### `POST /api/v1/python/menus/ocr`

메뉴판 이미지에서 OCR 방식으로 텍스트를 읽고 메뉴 목록을 추출합니다.

요청 형식:

- `multipart/form-data`
- `image`: 메뉴판 이미지 파일 (필수)

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "rawText": "중식\n김치찌개\n돈까스\n비빔밥",
    "menus": [
      { "menuName": "김치찌개" },
      { "menuName": "돈까스" },
      { "menuName": "비빔밥" }
    ]
  }
}
```

---

## 5) 메뉴판 OCR + 분석 API

### `POST /api/v1/python/menus/analyze-from-ocr`

메뉴판 OCR 결과를 바로 메뉴 분석으로 연결합니다.

요청 형식:

- `multipart/form-data`
- `image`: 메뉴판 이미지 파일 (필수)
- `startMenuId`: 응답 `menuId` 시작값 (선택, 기본값 `1`)

성공 응답 예시:

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "menuId": 1,
        "menuName": "김치찌개",
        "status": "SUCCESS",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "gemini-2.5-flash",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.92 }
        ],
        "allergies": [],
        "spicyLevel": 2
      }
    ]
  }
}
```

---

## 6) 이미지 메뉴 분석 API

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
        "status": "SUCCESS",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "gemini-2.5-flash",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.92 },
          { "ingredientCode": "SOYBEAN", "confidence": 0.88 }
        ],
        "allergies": [],
        "spicyLevel": 0
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
python3 -m pytest -q tests/live                # 단위 테스트 (메뉴 분리, 서비스, 리포지토리)
python3 -m pytest -q tests/integration          # 통합 테스트 (AI API, Spring 계약)
```

---

## AWS 배포 가이드 (친구가 README만 보고 배포)

이 서비스는 Dockerfile 없이도 배포 가능합니다. 현재 저장소 기준으로는 **EC2 + systemd + Nginx + ACM/Certbot** 구성이 가장 빠르고 안정적입니다.

### 권장 아키텍처

- **EC2 (Ubuntu 22.04)**: FastAPI(Uvicorn) 실행
- **systemd**: 프로세스 자동 재시작/부팅 시 자동 실행
- **Nginx**: 80/443 리버스 프록시
- **Route53 + 인증서**: 도메인/TLS
- **보안그룹**:
  - 인바운드: `22`(관리자 IP 제한), `80`, `443`
  - 아웃바운드: 기본 허용 (Gemini, 외부 메뉴 URL 호출 필요)

### 1) EC2 서버 준비

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

애플리케이션용 계정/디렉터리:

```bash
sudo mkdir -p /opt/ai-agent-crawler
sudo chown -R $USER:$USER /opt/ai-agent-crawler
cd /opt/ai-agent-crawler
```

소스 배포:

```bash
git clone <REPO_URL> .
git checkout DTO-확정
```

### 2) Python 런타임 설치

```bash
cd /opt/ai-agent-crawler
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3) 운영 환경변수 설정 (`.env`)

```bash
cd /opt/ai-agent-crawler
cp .env.example .env
```

최소 필수(운영 권장):

```env
GEMINI_API_KEY=YOUR_GEMINI_KEY
GEMINI_MODEL=gemini-2.5-flash
SERVICE_TIMEZONE=Asia/Seoul
AI_MAX_CONCURRENT_TASKS=4
# SSRF 방어 권장
CRAWL_SOURCE_ALLOWLIST=www.kumoh.ac.kr,kumoh.ac.kr
```

### 4) systemd 서비스 등록

`/etc/systemd/system/ai-agent-crawler.service` 생성:

```ini
[Unit]
Description=AI Agent Crawler FastAPI Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ai-agent-crawler
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/ai-agent-crawler/.env
ExecStart=/opt/ai-agent-crawler/.venv/bin/python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

적용:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-agent-crawler
sudo systemctl start ai-agent-crawler
sudo systemctl status ai-agent-crawler
```

로그 확인:

```bash
journalctl -u ai-agent-crawler -f
```

### 5) Nginx 리버스 프록시 설정

`/etc/nginx/sites-available/ai-agent-crawler`:

```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    client_max_body_size 15M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

활성화:

```bash
sudo ln -s /etc/nginx/sites-available/ai-agent-crawler /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6) HTTPS 적용 (권장)

옵션 A: Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.your-domain.com
```

옵션 B: ALB + ACM(팀 운영에 더 적합)

- ALB(443)에서 ACM 인증서 연결
- Target Group은 EC2:80 또는 EC2:8000
- 헬스체크는 `/docs` 또는 `/openapi.json` 권장

### 7) 배포 후 체크리스트

서버 내부 헬스 체크:

```bash
curl -sS http://127.0.0.1:8000/openapi.json | jq .openapi
```

외부 도메인 체크:

```bash
curl -sS https://api.your-domain.com/docs
```

샘플 API 호출:

```bash
curl -sS -X POST "https://api.your-domain.com/api/v1/python/menus/analyze" \
  -H "Content-Type: application/json" \
  -H "Accept-Language: ko" \
  -d '{"menus":[{"menuId":1,"menuName":"김치찌개"}]}'
```

### 8) 운영 시 반드시 확인할 설정값

| 키 | 필수 여부 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | 필수 | 분석/번역/OCR 모든 AI 기능에 필요 |
| `GEMINI_MODEL` | 권장 | 기본값 사용 가능하나 운영에서 고정 권장 |
| `SERVICE_TIMEZONE` | 권장 | `analyzedAt` 생성 타임존 |
| `AI_MAX_CONCURRENT_TASKS` | 권장 | 동시 AI 호출 수 |
| `CRAWL_SOURCE_ALLOWLIST` | 강력 권장 | 크롤링 `sourceUrl` 호스트 제한 (SSRF 방어) |
| `SPRING_API_TOKEN` | 선택 | Spring 내부 API 보호 시 Bearer 토큰 |
| `SPRING_API_KEY` | 선택 | Spring 내부 API가 X-API-Key 요구 시 |

### 9) 장애 대응 포인트

- `502/504` 다발: 외부 메뉴 사이트 응답 지연 가능성, `sourceUrl` 접근성 점검
- `AI_001` 응답: `GEMINI_API_KEY` 누락/오타
- OCR 결과 빈 값: 업로드 이미지 품질/해상도 확인, 메뉴판 crop 후 재시도
- 크롤링 차단: `CRAWL_SOURCE_ALLOWLIST` 설정값과 실제 도메인 일치 확인

---

## Spring Native API 상세

Spring WebClient가 직접 파싱할 수 있도록 `{success, data}` 래핑 없이 결과를 반환합니다.

### `POST /api/v1/crawl/meals`

식단 크롤링 (Wrapped 버전과 동일한 로직, 응답만 unwrapped).

**요청:**

```json
{
  "schoolName": "금오공과대학교",
  "cafeteriaName": "일품식당",
  "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
  "startDate": "2026-05-05",
  "endDate": "2026-05-11"
}
```

**응답 (200):**

```json
{
  "schoolName": "금오공과대학교",
  "cafeteriaName": "일품식당",
  "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
  "startDate": "2026-05-05",
  "endDate": "2026-05-11",
  "meals": [
    {
      "mealDate": "2026-05-05",
      "mealType": "BREAKFAST",
      "menus": [
        {"cornerName": "조식", "displayOrder": 1, "menuName": "다찬스페셜정식도시락"}
      ]
    },
    {
      "mealDate": "2026-05-05",
      "mealType": "LUNCH",
      "menus": [
        {"cornerName": "일품요리", "displayOrder": 1, "menuName": "김치우동"},
        {"cornerName": "일품요리", "displayOrder": 2, "menuName": "목살필라프"},
        {"cornerName": "일품요리", "displayOrder": 3, "menuName": "참치마요덮밥"}
      ]
    }
  ]
}
```

---

### `POST /api/v1/menus/analyze`

메뉴 AI 분석 (Wrapped 버전과 동일한 로직, 응답만 unwrapped). 응답 JSON에는 하위 호환용으로 `spicy_level`(snake_case) 키가 `spicyLevel`과 동일 값으로 **추가로** 포함될 수 있습니다. 신규 연동은 `spicyLevel`·`allergies`를 기준으로 하면 됩니다.

**요청:**

```json
{
  "menus": [{"menuId": 1, "menuName": "김치찌개"}]
}
```

**응답 (200):**

```json
{
  "results": [
    {
      "menuId": 1,
      "menuName": "김치찌개",
      "status": "SUCCESS",
      "reason": null,
      "modelName": "gemini",
      "modelVersion": "gemini-2.5-flash",
      "analyzedAt": "2026-05-12T12:00:00",
      "ingredients": [{"ingredientCode": "PORK", "confidence": 0.95}],
      "allergies": [{"allergyCode": "SOYBEAN", "confidence": 0.85}],
      "spicyLevel": 3,
      "spicy_level": 3
    }
  ]
}
```

---

### `POST /api/v1/translations`

자유 텍스트 번역.

**요청:**

```json
{
  "sourceLang": "ko",
  "targetLang": "en",
  "text": "이 메뉴에 땅콩이 들어가나요?"
}
```

**응답 (200):**

```json
{
  "translatedText": "Does this menu contain peanuts?"
}
```
