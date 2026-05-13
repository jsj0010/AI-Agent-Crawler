#!/usr/bin/env python3
"""Spring ↔ Python HTTP 연동을 **로컬에서** 최소 검증합니다.

1) Spring→Python (시뮬레이션): JVM 없이 `requests`로 Spring `RestClient`와 동일한
   `POST {base}/api/v1/crawl/meals` + JSON 본문을 보내 비래핑 응답을 확인합니다.

2) Python→Spring (시뮬레이션): 가짜 Spring HTTP 서버가 POST 본문을 받았는지
   `SpringRepository.post_json`으로 확인합니다.

실제 Spring Boot + DB를 띄우는 E2E는 포함하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


def _wait_http(url: str, timeout_sec: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
        except OSError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"서버 준비 시간 초과: {url}")


def verify_spring_calls_python_crawl(*, base_url: str) -> None:
    url = f"{base_url.rstrip('/')}/api/v1/crawl/meals"
    payload = {
        "schoolName": "금오공과대학교",
        "cafeteriaName": "일품식당",
        "sourceUrl": "https://www.kumoh.ac.kr/ko/restaurant01.do",
        "startDate": "2026-04-21",
        "endDate": "2026-04-22",
    }
    r = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json", "Accept-Language": "ko"},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"POST {url} -> HTTP {r.status_code}: {(r.text or '')[:500]}")
    body = r.json()
    if "success" in body:
        raise RuntimeError("비래핑 계약 위반: 응답에 success 키가 있습니다 (Spring PythonMealCrawlResponse 역직렬화 실패 가능).")
    for key in ("schoolName", "cafeteriaName", "sourceUrl", "startDate", "endDate", "meals"):
        if key not in body:
            raise RuntimeError(f"필드 누락: {key} in {list(body.keys())}")


def verify_python_posts_to_spring_mock() -> None:
    captured: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            captured["path"] = self.path
            captured["body"] = raw.decode("utf-8", errors="replace")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args: object) -> None:  # noqa: ARG002
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from app.repositories.spring_repository import SpringRepository

        url = f"http://127.0.0.1:{port}/api/internal/menu-ingest"
        payload = {"probe": "python-to-spring", "n": 1}
        res = SpringRepository().post_json(url=url, payload=payload, token="t1", api_key="k1")
        if res.status_code != 200:
            raise RuntimeError(f"mock Spring HTTP {res.status_code}: {res.text[:300]}")
        if "/api/internal/menu-ingest" not in (captured.get("path") or ""):
            raise RuntimeError(f"경로 불일치: {captured.get('path')}")
        body = json.loads(captured["body"])
        if body.get("probe") != "python-to-spring":
            raise RuntimeError(f"본문 불일치: {captured.get('body')[:200]}")
    finally:
        server.shutdown()
        thread.join(timeout=3)


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    import repo_env  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Spring↔Python HTTP 계약 로컬 검증")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Uvicorn 포트. 0이면 사용 가능한 포트를 자동 선택 (기본 0).",
    )
    args = parser.parse_args()

    repo_env.load_dotenv_from_repo_root()
    host = "127.0.0.1"
    port = args.port if args.port > 0 else _pick_free_port()
    base = f"http://{host}:{port}"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_http(f"{base}/health")
        print("[1/2] Spring→Python (HTTP 시뮬): POST /api/v1/crawl/meals …")
        verify_spring_calls_python_crawl(base_url=base)
        print("       OK — 비래핑 JSON 및 필수 키 확인")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("[2/2] Python→Spring (mock 수신): SpringRepository.post_json …")
    verify_python_posts_to_spring_mock()
    print("       OK — mock 서버가 POST 본문 수신")

    print("\n전체 통과: Spring이 Python을 부를 때의 계약(크롤) + Python이 Spring URL로 POST 하는 경로가 동작합니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
