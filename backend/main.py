"""SNUH 환자 정보 기반 수치 계산기 — FastAPI 진입점."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src import calculators, dependencies, settings, ui
from src.prefix import PrefixAliasMiddleware
from src.routers import calculators_router, health_router, patients_router
from src.snapshot.variables import current as current_variables

# 로깅: stdout 전용 (12-factor)
_level = getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper(), logging.INFO)
root = logging.getLogger()
root.setLevel(_level)
root.handlers.clear()
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(message)s", datefmt="%m/%d/%Y %I:%M:%S %p"))
root.addHandler(_h)
# access log 는 환자번호(경로)를 stdout 에 찍는다 — 끈다 (snuh-fhir 와 같은 원칙).
logging.getLogger("uvicorn.access").disabled = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.FHIR_MODE not in settings.FHIR_MODES:
        logging.error("[Lifespan] APP_FHIR_MODE=%r 는 알 수 없는 값입니다 (%s)", settings.FHIR_MODE, "/".join(settings.FHIR_MODES))
        raise RuntimeError("invalid APP_FHIR_MODE")
    if settings.FHIR_MODE == "http" and not settings.FHIR_TOKEN:
        logging.warning("[Lifespan] APP_FHIR_TOKEN 미설정 — 요청마다 X-Fhir-Token 헤더가 없으면 FHIR 호출이 401 입니다")
    if settings._DOTENV_LOADED:
        logging.info("[Lifespan] .env 적용: %s", ", ".join(settings._DOTENV_LOADED))
    logging.info("[Lifespan] FHIR source: %s", dependencies.describe_source())
    logging.info("[Lifespan] Calculators: %s", ", ".join(s.id for s in calculators.all_specs()))
    vm = current_variables()
    logging.info("[Lifespan] Variable map: %d variables%s", len(vm.defs),
                 f" (override {settings.VARIABLE_MAP_PATH})" if settings.VARIABLE_MAP_PATH else "")
    logging.info("[Lifespan] Lookback days: lab=%d vital=%d ecg=%d weight=%d", settings.LAB_LOOKBACK_DAYS,
                 settings.VITAL_LOOKBACK_DAYS, settings.ECG_LOOKBACK_DAYS, settings.WEIGHT_HISTORY_DAYS)
    logging.info("[Lifespan] Path prefix: %s", settings.PATH_PREFIX or "(none)")
    logging.info("[Lifespan] UI: %s", ui.describe())
    yield


app = FastAPI(
    title="SNUH Patient Calculator",
    version="0.1.0",
    docs_url=None, openapi_url=None, redoc_url=None,
    default_response_class=JSONResponse,
    lifespan=lifespan,
)
app.add_middleware(PrefixAliasMiddleware)

app.include_router(health_router)
app.include_router(calculators_router)
app.include_router(patients_router)
ui.install_ui(app)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, access_log=False)
