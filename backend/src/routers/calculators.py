"""계산기 스펙 목록 + 단건 계산."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src import calculators
from src.calculators.base import InputError
from src.snapshot.flags import flag_labels
from src.snapshot.variables import current as current_variables

router = APIRouter(prefix="/api", tags=["Calculators"])


class CalculateRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


@router.get("/calculators")
async def list_calculators() -> dict:
    vm = current_variables()
    return {
        "items": [s.to_dict() for s in calculators.all_specs()],
        "variables": {d.name: {"label": d.label, "unit": d.unit} for d in vm.defs},
        "flags": flag_labels(),
    }


@router.post("/calculate/{calc_id}")
async def calculate(calc_id: str, body: CalculateRequest) -> dict:
    spec = calculators.get(calc_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"알 수 없는 계산기: {calc_id}")
    try:
        return spec.run(body.inputs).to_dict()
    except InputError as e:
        raise HTTPException(status_code=400, detail={"message": e.message, "missing": e.missing, "invalid": e.invalid})
