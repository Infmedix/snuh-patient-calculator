"""환자 스냅샷 / 개요. 환자번호는 경로에 실리지만 access log 는 꺼져 있다 (main.py)."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from src import prefill
from src.dependencies import fhir_client
from src.fhir.client import FhirClient, FhirError, fetch_patient_data
from src.snapshot.extract import build_snapshot
from src.snapshot.flags import flag_labels
from src.snapshot.model import Snapshot
from src.snapshot.variables import current as current_variables

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Patients"])


# PAT 문제는 424(Failed Dependency) + code 로 돌려준다 — 401/403 을 그대로 내면 상위 gateway 가 계산기
# 자체의 로그인 문제로 오해해 가로챌 수 있고, 프런트는 code 로 「토큰 재등록」과 「접근 허용 요청」을 구분해 안내한다.
PAT_MISSING = {"code": "pat_missing",
               "message": "FHIR 조회 토큰이 없습니다. 서버 설정(APP_FHIR_TOKEN)에 서비스 계정 PAT 를 넣거나, 화면에서 본인 PAT 를 등록하세요."}
PAT_INVALID = {"code": "pat_invalid",
               "message": "FHIR 토큰을 snuh-fhir 가 거부했습니다 (형식 오류·폐기·만료). 서버의 APP_FHIR_TOKEN 또는 등록한 PAT 를 확인하세요."}
PAT_NO_ACCESS = {"code": "pat_no_access",
                 "message": "토큰 소유자에게 FHIR 접근 허용이 없습니다. snuh-fhir 관리자가 그 계정에 접근 허용을 부여해야 합니다."}


def _http_error(e: FhirError) -> HTTPException:
    if e.status == 404:
        return HTTPException(404, e.detail)
    if e.status == 401:
        return HTTPException(424, PAT_INVALID)
    if e.status == 403:
        return HTTPException(424, PAT_NO_ACCESS)
    if e.status in (503, 504):
        return HTTPException(503, e.detail)
    if e.status == 400:
        return HTTPException(400, e.detail)
    return HTTPException(502, e.detail)


async def _snapshot(pid: str, client: FhirClient, now: datetime) -> Snapshot:
    pid = pid.strip()
    if not pid or len(pid) > 32 or "/" in pid:
        raise HTTPException(400, "환자번호 형식이 올바르지 않습니다")
    if not client.has_token:
        raise HTTPException(424, PAT_MISSING)
    try:
        raw = await fetch_patient_data(client, pid, now)
    except FhirError as e:
        raise _http_error(e)
    return build_snapshot(pid, raw.patient, raw.lab, raw.clinical, raw.exam, raw.conditions,
                          current_variables(), now, warnings=raw.warnings)


@router.get("/patients/{pid}/snapshot")
async def get_snapshot(pid: str, client: FhirClient = Depends(fhir_client)) -> dict:
    snap = await _snapshot(pid, client, datetime.now())
    return snap.model_dump()


@router.get("/patients/{pid}/overview")
async def get_overview(pid: str, client: FhirClient = Depends(fhir_client)) -> dict:
    now = datetime.now()
    snap = await _snapshot(pid, client, now)
    return {"snapshot": snap.model_dump(), "flag_labels": flag_labels(), "calculators": prefill.overview(snap, now)}
