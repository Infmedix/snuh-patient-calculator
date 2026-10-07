"""CrCl — Cockcroft-Gault 크레아티닌 청소율.

CrCl = (140 − 나이) × 체중 / (72 × Scr) × 0.85 [여성]   (Nephron 1976;16:31-41)
체중 기준: 실제체중 / 이상체중(Devine: 남 50 + 0.9·(cm−152.4), 여 45.5 + 0.9·(cm−152.4)) /
보정체중(IBW + 0.4·(실제 − IBW)). 약물 용량 조절 문헌은 대개 실제체중 또는 보정체중을 쓴다.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputError, InputSpec, Option, Result, Scale, register
from src.calculators.common import age_input, sex_input


def ideal_body_weight(height_cm: float, sex: str) -> float:
    base = 45.5 if sex == "F" else 50.0
    return base + 0.9 * (height_cm - 152.4)


def compute(i: dict) -> Result:
    basis = i["weight_basis"]
    actual = i["weight_kg"]
    details = [Detail("실제체중", f"{actual:g} kg")]
    if basis == "actual":
        weight = actual
    else:
        if i.get("height_cm") is None:
            raise InputError("이상체중/보정체중 기준에는 신장이 필요합니다", missing=["height_cm"])
        ibw = ideal_body_weight(i["height_cm"], i["sex"])
        if ibw <= 0:
            raise InputError("신장이 너무 작아 이상체중을 계산할 수 없습니다", invalid={"height_cm": "Devine 식 범위 밖"})
        details.append(Detail("이상체중 (Devine)", f"{ibw:.1f} kg"))
        if basis == "ideal":
            weight = ibw
        else:
            weight = ibw + 0.4 * (actual - ibw)
            details.append(Detail("보정체중", f"{weight:.1f} kg"))
    crcl = (140 - i["age"]) * weight / (72 * i["creatinine"])
    if i["sex"] == "F":
        crcl *= 0.85
    if crcl >= 90:
        label, sev = "정상 범위", "ok"
    elif crcl >= 60:
        label, sev = "경도 감소", "ok"
    elif crcl >= 30:
        label, sev = "중등도 감소 — 신기능 용량 조절 확인", "warn"
    elif crcl >= 15:
        label, sev = "중증 감소", "danger"
    else:
        label, sev = "신부전 수준", "danger"
    notes = ["약물 용량 조절 판단은 각 약물의 허가사항이 지정한 식·체중 기준을 따르세요."]
    if basis == "actual" and i.get("height_cm") is not None:
        ibw = ideal_body_weight(i["height_cm"], i["sex"])
        if ibw > 0 and actual > ibw * 1.3:
            notes.append("실제체중이 이상체중의 130% 를 넘습니다 — 보정체중 기준도 확인하세요.")
    return Result(value=round(crcl, 1), unit="mL/min", label=label, severity=sev, details=details, notes=notes)


SPEC = register(CalculatorSpec(
    id="crcl", name="CrCl (Cockcroft-Gault)", group="신체·신장",
    description="크레아티닌 청소율 추정 — 약물 용량 조절 판단",
    inputs=(
        age_input(),
        sex_input(),
        InputSpec("weight_kg", "체중", "number", unit="kg", minimum=1, maximum=500, variable="weight_kg"),
        InputSpec("creatinine", "혈청 크레아티닌", "number", unit="mg/dL", minimum=0.1, maximum=50, variable="creatinine"),
        InputSpec("height_cm", "신장", "number", unit="cm", minimum=30, maximum=300, required=False, variable="height_cm",
                  help="이상체중·보정체중 기준일 때 필요"),
        InputSpec("weight_basis", "체중 기준", "select", default="actual",
                  options=(Option("actual", "실제체중"), Option("ideal", "이상체중"), Option("adjusted", "보정체중"))),
    ),
    compute=compute,
    references=("Cockcroft DW, Gault MH. Nephron 1976;16:31-41.", "Devine BJ. Drug Intell Clin Pharm 1974;8:650-5."),
    scale=Scale(0, 120, (Band(15, "신부전", "danger"), Band(30, "중증 감소", "danger"), Band(60, "중등도 감소", "warn"),
                         Band(90, "경도 감소", "ok"), Band(None, "정상", "ok"))),
    guide="약물 용량 조절에 쓰는 신기능 추정치. 대부분의 허가사항이 이 식(Cockcroft-Gault)을 기준으로 용량 구간을 정합니다.",
))
