"""환경변수 기반 런타임 설정. 새 항목을 추가하면 `.env.example` 에도 반드시 반영할 것.

값은 모듈 속성으로 읽는다(`settings.FHIR_BASE_URL`). import 시점에 상수로 복사해 쓰면
테스트에서 monkeypatch 가 먹지 않는다 (snuh-fhir 와 같은 규칙).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _BACKEND_DIR.parent


def load_dotenv(path: Optional[Path] = None) -> list[str]:
    """저장소 루트(또는 backend/)의 `.env` 를 읽어 **아직 없는** 환경변수만 채운다.

    docker compose 는 env_file 로 넣어 주지만 로컬 `uv run uvicorn` 은 아무것도 읽지 않아
    APP_FHIR_MODE=mock 을 빠뜨리면 snuh-fhir(localhost:8000) 접속 실패로 502 가 난다 - 그 함정 제거.
    셸에서 직접 지정한 값이 항상 우선한다. 형식: `KEY=value`, `#` 주석, 따옴표 허용. 외부 의존성 없음.
    """
    candidates = [path] if path else [_REPO_DIR / ".env", _BACKEND_DIR / ".env"]
    loaded: list[str] = []
    for p in candidates:
        if p is None or not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
        break
    return loaded


_DOTENV_LOADED = load_dotenv()


def _env(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r 는 정수가 아닙니다. 기본값 %s 사용.", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%s 는 허용 최소값 %s 미만입니다. 기본값 %s 사용.", name, value, minimum, default)
        return default
    return value


def _float_env(name: str, default: float, minimum: float = 0.0) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s=%r 는 숫자가 아닙니다. 기본값 %s 사용.", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%s 는 허용 최소값 %s 미만입니다. 기본값 %s 사용.", name, value, minimum, default)
        return default
    return value


# ===== FHIR 데이터 소스 =====
# http = snuh-fhir 호출 (운영). mock = backend/fixtures 의 번들 (개발·시연·테스트).
FHIR_MODES = ("http", "mock")
FHIR_MODE = (_env("APP_FHIR_MODE") or "http").lower()
# snuh-fhir 기본 URL - gateway 경유는 https://<host>/apps/runtime/fhir, 클러스터 내부는 http://snuh-fhir:8000
FHIR_BASE_URL = (_env("APP_FHIR_BASE_URL") or "http://localhost:8000").rstrip("/")
# 서비스 계정 PAT. 요청의 X-Fhir-Token 헤더가 있으면 그쪽이 우선. 값은 어디에도 로그하지 않는다.
FHIR_TOKEN = _env("APP_FHIR_TOKEN")
FHIR_TIMEOUT_SECONDS = _float_env("APP_FHIR_TIMEOUT_SECONDS", 30.0, minimum=1.0)
# mock 모드 fixture 디렉터리 - `patients/{환자번호}.json` (Bundle type=collection)
FIXTURES_DIR = _env("APP_FIXTURES_DIR") or str(_BACKEND_DIR / "fixtures")

# ===== 조회 범위 =====
# "가장 최근 값" 을 고르기 위해 뒤로 훑는 기간. 길수록 snuh-fhir·ODS 부하가 커진다.
LAB_LOOKBACK_DAYS = _int_env("APP_LAB_LOOKBACK_DAYS", 180)
VITAL_LOOKBACK_DAYS = _int_env("APP_VITAL_LOOKBACK_DAYS", 30)
ECG_LOOKBACK_DAYS = _int_env("APP_ECG_LOOKBACK_DAYS", 365)
# 체중 이력(NRS-2002 체중감소율)용 - 활력징후 기간과 별개로 더 길게 본다.
WEIGHT_HISTORY_DAYS = _int_env("APP_WEIGHT_HISTORY_DAYS", 100)
# 심전도 exam 검색의 code(처방명 LIKE) 값
ECG_ORDER_NAME = _env("APP_ECG_ORDER_NAME") or "심전도"
# 페이지 크기(snuh-fhir 상한 1000)와 리소스별 최대 페이지 수 - 환자 1명 조회의 비용 상한
PAGE_SIZE = min(_int_env("APP_PAGE_SIZE", 1000), 1000)
MAX_PAGES = _int_env("APP_MAX_PAGES", 3)
# 자동 채움값이 이보다 오래되면 화면에 「오래됨」 태그 (계산은 그대로 - 판단은 사용자)
STALE_AFTER_DAYS = _int_env("APP_STALE_AFTER_DAYS", 7)

# 항목명 → 정규 변수 별칭 덮어쓰기 (YAML). 미설정 = 내장 별칭만.
VARIABLE_MAP_PATH = _env("APP_VARIABLE_MAP_PATH")

# ===== 배포 =====
# 외부 공개 경로 prefix (예: /apps/runtime/calculator). 미설정 = prefix 없음.
# snuhai 앱 스토어(snuhai-paas)는 컨테이너에 BASE_URL=/apps/runtime/{slug} 를 주입한다 - APP_PATH_PREFIX 가 없으면 그 값을 쓴다.
PATH_PREFIX = _env("APP_PATH_PREFIX") or _env("BASE_URL") or ""
# 빌드된 프런트(dist) 경로. 없으면 /ui 만 404, 부팅 정상.
UI_DIST_DIR = _env("APP_UI_DIST_DIR") or str(_BACKEND_DIR.parent / "frontend" / "dist")
