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


def _http_error(e: FhirError) -> HTTPException:
    # 401/403 은 **이 서비스의** 설정·권한 문제이므로 502 로 바꿔 전달 (브라우저가 자기 토큰 문제로 오해하지 않게)
    if e.status == 404:
        return HTTPException(404, e.detail)
    if e.status in (401, 403):
        return HTTPException(502, e.detail)
    if e.status in (503, 504):
        return HTTPException(503, e.detail)
    if e.status == 400:
        return HTTPException(400, e.detail)
    return HTTPException(502, e.detail)


async def _snapshot(pid: str, client: FhirClient, now: datetime) -> Snapshot:
    pid = pid.strip()
    if not pid or len(pid) > 32 or "/" in pid:
        raise HTTPException(400, "환자번호 형식이 올바르지 않습니다")
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
