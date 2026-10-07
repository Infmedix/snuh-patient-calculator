"""snuh-fhir 클라이언트 — HTTP(운영) 와 mock(fixture) 두 구현, 같은 인터페이스.

규칙 (snuh-fhir Common_API.md):
- 모든 FHIR 호출에 `Authorization: Bearer <PAT>`. 401 → 토큰 문제, 403 → 접근 권한(사람 단위) 문제, 503 → 일시 장애.
- `Bundle.total` 은 이번 페이지 건수. `total == _count` 면 다음 페이지가 있을 수 있다 → `_offset` 증가.
- 토큰 값은 로그·예외 메시지·URL 에 싣지 않는다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol

import httpx

logger = logging.getLogger(__name__)


class FhirError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class FhirClient(Protocol):
    async def get(self, path: str, params: Optional[dict] = None) -> dict: ...
    def describe(self) -> str: ...


# ===== HTTP =====

class HttpFhirClient:
    def __init__(self, base_url: str, token: Optional[str], timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    def describe(self) -> str:
        return f"http {self.base_url} (token {'set' if self._token else 'missing'})"

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        headers = {"Accept": "application/fhir+json, application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                res = await c.get(url, params=params, headers=headers)
        except httpx.TimeoutException:
            raise FhirError(504, f"FHIR 서버 응답 시간 초과 ({path})")
        except httpx.HTTPError as e:
            raise FhirError(502, f"FHIR 서버에 연결할 수 없습니다 ({e.__class__.__name__})")
        if res.status_code >= 400:
            raise FhirError(res.status_code, _detail(res, path))
        try:
            return res.json()
        except ValueError:
            raise FhirError(502, f"FHIR 응답이 JSON 이 아닙니다 ({path})")


def _detail(res: httpx.Response, path: str) -> str:
    try:
        body = res.json()
    except ValueError:
        body = None
    msg = None
    if isinstance(body, dict):
        if body.get("resourceType") == "OperationOutcome":
            issues = body.get("issue") or []
            msg = "; ".join(i.get("diagnostics") or i.get("code", "") for i in issues if isinstance(i, dict))
        elif isinstance(body.get("detail"), str):
            msg = body["detail"]
    s = res.status_code
    if s == 401:
        return "FHIR 토큰이 없거나 거부되었습니다 (APP_FHIR_TOKEN 또는 X-Fhir-Token 확인)" + (f": {msg}" if msg else "")
    if s == 403:
        return "FHIR 접근 권한이 없습니다 — 토큰 소유자에게 FHIR 접근 허용이 부여되어야 합니다" + (f": {msg}" if msg else "")
    if s == 404:
        return msg or f"FHIR 리소스를 찾을 수 없습니다 ({path})"
    if s == 503:
        return "FHIR 서버가 일시적으로 요청을 받지 못합니다 (잠시 후 재시도)"
    return msg or f"FHIR 호출 실패 HTTP {s} ({path})"


# ===== mock (fixtures) =====

class MockFhirClient:
    """`<fixtures>/patients/{환자번호}.json` (Bundle collection) 을 snuh-fhir 검색처럼 걸러서 돌려준다.

    지원 파라미터: Patient/{id}, Observation?patient&category&date(ge/gt/le/lt)&code&_count&_offset,
    Condition?patient&_count&_offset. 그 외는 무시한다.
    """

    def __init__(self, fixtures_dir: str):
        self.dir = Path(fixtures_dir)

    def describe(self) -> str:
        return f"mock {self.dir}"

    def _load(self, pid: str) -> Optional[list[dict]]:
        p = self.dir / "patients" / f"{pid}.json"
        if not p.is_file() or not pid or "/" in pid or ".." in pid:
            return None
        bundle = json.loads(p.read_text(encoding="utf-8"))
        return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]

    def patients(self) -> list[str]:
        d = self.dir / "patients"
        return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        params = params or {}
        path = path.strip("/")
        if path == "health":
            return {"status": "ok"}
        if path.startswith("Patient/"):
            pid = path.split("/", 1)[1]
            res = self._load(pid)
            if res is None:
                raise FhirError(404, f"환자 {pid} 를 찾을 수 없습니다")
            for r in res:
                if r.get("resourceType") == "Patient":
                    return r
            raise FhirError(404, f"환자 {pid} 를 찾을 수 없습니다")
        pid = params.get("patient")
        if path in ("Observation", "Condition"):
            if not pid:
                raise FhirError(400, "patient 가 필요합니다")
            res = self._load(pid) or []
            rows = [r for r in res if r.get("resourceType") == path]
            if path == "Observation":
                cat = params.get("category", "laboratory")
                rows = [r for r in rows if _category(r) == cat]
                code = params.get("code")
                if code:
                    rows = [r for r in rows if code.lower() in ((r.get("code") or {}).get("text") or "").lower()]
                rows = [r for r in rows if _date_ok(r.get("effectiveDateTime"), params)]
                rows.sort(key=lambda r: r.get("effectiveDateTime") or "", reverse=True)
            else:
                rows.sort(key=lambda r: r.get("recordedDate") or "", reverse=True)
            count = int(params.get("_count", 50))
            offset = int(params.get("_offset", 0))
            page = rows[offset:offset + count]
            return {"resourceType": "Bundle", "type": "searchset", "total": len(page),
                    "entry": [{"resource": r} for r in page]}
        raise FhirError(404, f"mock 이 지원하지 않는 경로: {path}")


def _category(res: dict) -> str:
    for c in res.get("category") or ():
        for cd in c.get("coding") or ():
            if cd.get("code"):
                return cd["code"]
    return ""


def _date_ok(when: Optional[str], params: dict) -> bool:
    dates = params.get("date")
    if not dates:
        return True
    if isinstance(dates, str):
        dates = [dates]
    if not when:
        return False
    w = when[:10]
    for d in dates:
        op, val = (d[:2], d[2:]) if d[:2] in ("ge", "gt", "le", "lt", "eq") else ("eq", d)
        val = val[:10]
        if op == "ge" and not w >= val:
            return False
        if op == "gt" and not w > val:
            return False
        if op == "le" and not w <= val:
            return False
        if op == "lt" and not w < val:
            return False
        if op == "eq" and w != val:
            return False
    return True


# ===== 페이지 순회 + 환자 1명 수집 =====

async def search_all(client: FhirClient, path: str, params: dict, page_size: int, max_pages: int) -> list[dict]:
    """`total == _count` 인 동안 `_offset` 을 늘려 번들을 모은다. 상한에 걸리면 경고 로그 (잘림 가능)."""
    bundles: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        b = await client.get(path, {**params, "_count": page_size, "_offset": offset})
        bundles.append(b)
        n = len(b.get("entry") or [])
        if n < page_size:
            return bundles
        offset += page_size
    logger.warning("[fhir] %s 페이지 상한(%d) 도달 — 더 오래된 기록은 보지 않았습니다", path, max_pages)
    return bundles


@dataclass
class RawPatientData:
    patient: Optional[dict]
    lab: list[dict] = field(default_factory=list)
    clinical: list[dict] = field(default_factory=list)
    exam: list[dict] = field(default_factory=list)
    conditions: Optional[list[dict]] = None     # None = 조회 실패
    warnings: list[str] = field(default_factory=list)


def _since(now: datetime, days: int) -> str:
    from datetime import timedelta
    return "ge" + (now - timedelta(days=days)).date().isoformat()


async def fetch_patient_data(client: FhirClient, pid: str, now: datetime) -> RawPatientData:
    """Patient 는 실패하면 그대로 올리고(404 등), 나머지 네 호출은 실패를 경고로 강등한다."""
    import asyncio
    from src import settings

    patient = await client.get(f"Patient/{pid}")

    jobs = {
        "lab": search_all(client, "Observation", {"patient": pid, "category": "laboratory",
                                                  "date": _since(now, settings.LAB_LOOKBACK_DAYS)},
                          settings.PAGE_SIZE, settings.MAX_PAGES),
        "clinical": search_all(client, "Observation", {"patient": pid, "category": "clinical",
                                                       "date": _since(now, max(settings.VITAL_LOOKBACK_DAYS, settings.WEIGHT_HISTORY_DAYS))},
                               settings.PAGE_SIZE, settings.MAX_PAGES),
        "exam": search_all(client, "Observation", {"patient": pid, "category": "exam", "code": settings.ECG_ORDER_NAME,
                                                   "date": _since(now, settings.ECG_LOOKBACK_DAYS)},
                           min(settings.PAGE_SIZE, 200), 1),
        "conditions": search_all(client, "Condition", {"patient": pid}, settings.PAGE_SIZE, min(settings.MAX_PAGES, 2)),
    }
    results = await asyncio.gather(*jobs.values(), return_exceptions=True)
    data = RawPatientData(patient=patient)
    labels = {"lab": "검사실 검사", "clinical": "활력징후·간호기록", "exam": "심전도", "conditions": "진단"}
    for key, r in zip(jobs.keys(), results):
        if isinstance(r, BaseException):
            msg = r.detail if isinstance(r, FhirError) else r.__class__.__name__
            logger.warning("[fhir] %s 조회 실패: %s", key, msg)
            data.warnings.append(f"{labels[key]} 조회 실패 — {msg}")
            if key != "conditions":
                setattr(data, key, [])
            continue
        setattr(data, key, r)
    return data
