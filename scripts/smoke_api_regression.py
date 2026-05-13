"""내부 연동 최소 API 회귀 스모크 테스트 스크립트.

기본 동작:
- uvicorn 서버를 자동 실행
- 최소 핵심 엔드포인트 호출
- 성공/실패 케이스 검증
- 서버 자동 종료
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

import requests


def _pretty(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def _request(method: str, url: str, **kwargs):
    return requests.request(method=method, url=url, timeout=30, **kwargs)


def _wait_for_server(base_url: str, timeout_sec: int = 25) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            resp = _request("GET", f"{base_url}/health")
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("서버 시작 대기 시간 초과")


def _assert_status(
    resp: requests.Response,
    expected_status: int | tuple[int, ...],
    label: str,
) -> None:
    allowed = (expected_status,) if isinstance(expected_status, int) else expected_status
    if resp.status_code not in allowed:
        body = ""
        try:
            body = _pretty(resp.json())
        except Exception:
            body = (resp.text or "")[:500]
        raise AssertionError(
            f"{label}: status={resp.status_code} expected={allowed}\nresponse={body}"
        )


def run_suite(base_url: str) -> None:
    tests = []

    # 정상 케이스
    tests.append(
        (
            "GET /health",
            _request("GET", f"{base_url}/health"),
            200,
        )
    )
    tests.append(
        (
            "POST /api/v1/python/meals/crawl (invalid range)",
            _request(
                "POST",
                f"{base_url}/api/v1/python/meals/crawl",
                json={
                    "schoolName": "금오공과대학교",
                    "cafeteriaName": "일품식당",
                    "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
                    "startDate": "2026-05-01",
                    "endDate": "2026-04-27",
                },
            ),
            400,
        )
    )
    tests.append(
        (
            "POST /api/v1/crawl/meals Spring-native (invalid range)",
            _request(
                "POST",
                f"{base_url}/api/v1/crawl/meals",
                json={
                    "schoolName": "금오공과대학교",
                    "cafeteriaName": "일품식당",
                    "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
                    "startDate": "2026-05-01",
                    "endDate": "2026-04-27",
                },
            ),
            400,
        )
    )
    tests.append(
        (
            "POST /api/v1/python/menus/analyze",
            _request(
                "POST",
                f"{base_url}/api/v1/python/menus/analyze",
                json={"menus": [{"menuId": 1, "menuName": "김치찌개"}]},
            ),
            (200, 500),
        )
    )
    tests.append(
        (
            "POST /api/v1/python/menus/translate",
            _request(
                "POST",
                f"{base_url}/api/v1/python/menus/translate",
                json={
                    "menus": [{"menuId": 1, "menuName": "김치찌개"}],
                    "targetLanguages": ["en"],
                },
            ),
            (200, 500),
        )
    )
    # 이미지 분석 라우트는 앱 조립에 포함되지 않은 배포마다 다를 수 있어 스모크에서 제외합니다.
    tests.append(
        (
            "GET /openapi.json (앱 인증 스텁 경로 미포함 확인)",
            _request("GET", f"{base_url}/openapi.json"),
            200,
        )
    )

    passed = 0
    for label, resp, expected in tests:
        _assert_status(resp, expected, label)

        if resp.status_code == 400:
            b = resp.json()
            if "Spring-native" in label:
                if "message" not in b and not (b.get("success") is False and b.get("code")):
                    raise AssertionError(
                        f"{label}: Spring-native 400은 message 또는 v1 오류(success/code) 형태여야 합니다."
                    )
            elif "python/meals/crawl" in label:
                if b.get("success") is not False:
                    raise AssertionError(f"{label}: 래핑 API는 success=false여야 합니다.")

        if "/python/menus/analyze" in resp.url or "/python/menus/translate" in resp.url:
            body = resp.json()
            if resp.status_code == 200:
                if body.get("success") is not True:
                    raise AssertionError(f"{label}: HTTP 200일 때 success=true 여야 합니다.")
            elif resp.status_code == 500:
                if body.get("code") != "AI_001":
                    raise AssertionError(f"{label}: HTTP 500일 때 code=AI_001 (미구성) 여야 합니다.")
            else:
                raise AssertionError(f"{label}: 예상하지 않은 상태 코드 {resp.status_code}")

        if "/openapi.json" in resp.url:
            body = resp.json()
            paths = body.get("paths", {})
            if "/auth/login" in paths or "/api/v1/settings/language" in paths:
                raise AssertionError("OpenAPI에 /auth/login 등 앱 전용 스텁 경로가 노출되어 있습니다.")
        print(f"[PASS] {label} -> {resp.status_code}")
        passed += 1

    print(f"\n총 {passed}건 테스트 통과")


def main() -> int:
    parser = argparse.ArgumentParser(description="내부 연동 최소 API 회귀 스모크 테스트")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--use-existing-server",
        action="store_true",
        help="이미 실행 중인 서버를 사용하고 자동 기동/종료를 하지 않습니다.",
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    server_proc = None

    try:
        if not args.use_existing_server:
            server_proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "user_features.live_service:app",
                    "--host",
                    args.host,
                    "--port",
                    str(args.port),
                ],
                env={**os.environ},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _wait_for_server(base_url)
            print("서버 자동 기동 완료")

        run_suite(base_url)
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("서버 자동 종료 완료")


if __name__ == "__main__":
    raise SystemExit(main())
