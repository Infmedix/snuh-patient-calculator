"""liveness / readiness. liveness 는 외부 왕복 없음 — FHIR 장애가 재시작 루프가 되면 안 된다."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response

from src import settings
from src.dependencies import make_client
from src.fhir.client import FhirError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """snuh-fhir `/health` 왕복 (mock 모드는 fixture 디렉터리만 확인). 실패 503."""
    try:
        if settings.FHIR_MODE == "mock":
            n = len(make_client().patients())  # type: ignore[attr-defined]
            return {"status": "ok", "fhir": "mock", "fixtures": n}
        await make_client().get("health")
        return {"status": "ok", "fhir": "ok"}
    except FhirError as e:
        logger.warning("[Health] readiness 실패 — FHIR %s %s", e.status, e.detail)
        response.status_code = 503
        return {"status": "unavailable", "fhir": "error", "detail": e.detail}
    except Exception:
        logger.warning("[Health] readiness 실패", exc_info=True)
        response.status_code = 503
        return {"status": "unavailable", "fhir": "error"}
