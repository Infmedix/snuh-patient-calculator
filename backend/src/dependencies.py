"""요청 단위 의존성 - FHIR 클라이언트 선택 (mode·토큰)."""

from __future__ import annotations

from typing import Optional

from fastapi import Header

from src import settings
from src.fhir.client import FhirClient, HttpFhirClient, MockFhirClient

TOKEN_HEADER = "X-Fhir-Token"


def make_client(token_override: Optional[str] = None) -> FhirClient:
    if settings.FHIR_MODE == "mock":
        return MockFhirClient(settings.FIXTURES_DIR)
    token = (token_override or "").strip() or settings.FHIR_TOKEN
    return HttpFhirClient(settings.FHIR_BASE_URL, token, settings.FHIR_TIMEOUT_SECONDS)


def fhir_client(x_fhir_token: Optional[str] = Header(default=None, alias=TOKEN_HEADER)) -> FhirClient:
    """요청에 X-Fhir-Token 이 있으면 그 PAT 로, 없으면 서비스 계정 PAT 로 호출한다."""
    return make_client(x_fhir_token)


def describe_source() -> str:
    if settings.FHIR_MODE == "mock":
        return MockFhirClient(settings.FIXTURES_DIR).describe()
    return HttpFhirClient(settings.FHIR_BASE_URL, settings.FHIR_TOKEN).describe()
