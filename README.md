# AI-Agent-Crawler

Spring Boot 내부 호출 전용 Python API 서버입니다. 현재는 아래 API를 제공합니다.

- `POST /api/v1/python/meals/crawl`
- `POST /api/v1/python/menus/analyze`
- `POST /api/v1/python/menus/ocr`
- `POST /api/v1/python/menus/analyze-from-ocr`
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
  - `Content-Type`: 기본은 `application/json`, 이미지 업로드 API는 `multipart/form-data`
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
| `POST` | `/api/v1/python/menus/ocr` | 메뉴판 이미지 OCR 추출 |
| `POST` | `/api/v1/python/menus/analyze-from-ocr` | 메뉴판 OCR 후 연속 분석 |
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
        "status": "COMPLETED",
        "reason": null,
        "modelName": "gemini",
        "modelVersion": "2.5",
        "analyzedAt": "2026-04-15T09:30:00",
        "ingredients": [
          { "ingredientCode": "PORK", "confidence": 0.92 }
        ]
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
