"""eGFR — CKD-EPI 2021 크레아티닌 식 (인종 변수 없음).

eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^−1.200 × 0.9938^Age × 1.012 [여성]
  κ = 0.7(여) / 0.9(남), α = −0.241(여) / −0.302(남)
Inker LA et al. N Engl J Med 2021;385:1737-49.
KDIGO 2012 분류: G1 ≥90, G2 60–89, G3a 45–59, G3b 30–44, G4 15–29, G5 <15.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register
from src.calculators.common import age_input, sex_input

STAGES = (
    (90, "G1 — 정상 또는 높음", "ok"),
    (60, "G2 — 경도 감소", "ok"),
    (45, "G3a — 경도~중등도 감소", "warn"),
    (30, "G3b — 중등도~중증 감소", "warn"),
    (15, "G4 — 중증 감소", "danger"),
    (0, "G5 — 신부전", "danger"),
)


def ckd_epi_2021(creatinine: float, age: float, sex: str) -> float:
    female = sex == "F"
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = creatinine / kappa
    egfr = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938 ** age
    if female:
        egfr *= 1.012
    return egfr


def compute(i: dict) -> Result:
    egfr = ckd_epi_2021(i["creatinine"], i["age"], i["sex"])
    for cut, label, sev in STAGES:
        if egfr >= cut:
            break
    return Result(
        value=round(egfr, 1), unit="mL/min/1.73m²", label=label, severity=sev,
        details=[Detail("혈청 크레아티닌", f"{i['creatinine']:g} mg/dL"), Detail("나이", f"{i['age']:g}세"),
                 Detail("성별", "여" if i["sex"] == "F" else "남")],
        notes=["CKD-EPI 2021 (인종 변수 없음). 급성 신손상·극단적 체격·근육량 이상에서는 부정확할 수 있습니다.",
               "CKD 진단은 3개월 이상 지속된 소견이 필요합니다 (KDIGO)."],
    )


SPEC = register(CalculatorSpec(
    id="egfr", name="eGFR (CKD-EPI 2021)", group="신체·신장",
    description="추정 사구체여과율 — 신장 기능 평가",
    inputs=(
        InputSpec("creatinine", "혈청 크레아티닌", "number", unit="mg/dL", minimum=0.1, maximum=50, variable="creatinine"),
        age_input(),
        sex_input(),
    ),
    compute=compute,
    references=("Inker LA et al. NEJM 2021;385:1737-49.", "KDIGO 2012 CKD Guideline."),
    scale=Scale(0, 120, (Band(15, "G5 신부전", "danger"), Band(30, "G4", "danger"), Band(45, "G3b", "warn"),
                         Band(60, "G3a", "warn"), Band(90, "G2", "ok"), Band(None, "G1", "ok"))),
    guide="혈청 크레아티닌·나이·성별로 사구체여과율을 추정합니다. 60 미만이 3개월 이상 지속되면 만성콩팥병(CKD G3 이상)입니다.",
))
