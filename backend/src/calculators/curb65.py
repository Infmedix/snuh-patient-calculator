"""CURB-65 — 지역사회획득 폐렴 중증도.

C 새로 생긴 의식 혼미, U 혈중 요소 >7 mmol/L (BUN >19 mg/dL), R 호흡수 ≥30, B SBP <90 또는 DBP ≤60, 65 나이 ≥65.
0–1 저위험(외래), 2 중등도(단기 입원·감시), 3–5 중증(입원, 4–5 는 중환자실 고려).
Lim WS et al. Thorax 2003;58:377-82. 30일 사망률: 0 0.6% · 1 2.7% · 2 6.8% · 3 14% · 4–5 27.8%.
"""

from __future__ import annotations

from src.calculators.base import CalculatorSpec, Detail, InputSpec, Result, register
from src.calculators.common import age_input

MORTALITY = {0: "0.6%", 1: "2.7%", 2: "6.8%", 3: "14%", 4: "27.8%", 5: "27.8%"}


def compute(i: dict) -> Result:
    items = [
        ("의식 혼미 (C)", i["confusion"], "예" if i["confusion"] else "아니오"),
        ("BUN >19 mg/dL (U)", i["bun"] > 19, f"{i['bun']:g} mg/dL"),
        ("호흡수 ≥30 (R)", i["rr"] >= 30, f"{i['rr']:g}/분"),
        ("SBP <90 또는 DBP ≤60 (B)", i["sbp"] < 90 or i["dbp"] <= 60, f"{i['sbp']:g}/{i['dbp']:g} mmHg"),
        ("나이 ≥65", i["age"] >= 65, f"{i['age']:g}세"),
    ]
    details = [Detail(l, t, 1 if c else 0) for l, c, t in items]
    score = sum(1 for _, c, _ in items if c)
    if score <= 1:
        label, sev = "저위험 — 외래 치료 고려", "ok"
    elif score == 2:
        label, sev = "중등도 — 단기 입원 또는 병원 감독 외래", "warn"
    elif score == 3:
        label, sev = "중증 — 입원 치료", "danger"
    else:
        label, sev = "중증 — 중환자실 평가", "danger"
    return Result(value=score, unit="점", label=label, severity=sev, details=details,
                  notes=[f"30일 사망률 참고 {MORTALITY[score]} (Lim 2003).",
                         "BUN 19 mg/dL ≈ urea 7 mmol/L. 의식 혼미는 새로 생긴 것(AMT ≤8)만 해당합니다."])


SPEC = register(CalculatorSpec(
    id="curb65", name="CURB-65", group="중증도",
    description="지역사회획득 폐렴 중증도 평가",
    inputs=(
        InputSpec("confusion", "새로 생긴 의식 혼미", "boolean", default=False),
        InputSpec("bun", "BUN", "number", unit="mg/dL", minimum=0, maximum=300, variable="bun"),
        InputSpec("rr", "호흡수", "number", unit="/분", minimum=0, maximum=100, variable="rr"),
        InputSpec("sbp", "수축기 혈압", "number", unit="mmHg", minimum=20, maximum=300, variable="sbp"),
        InputSpec("dbp", "이완기 혈압", "number", unit="mmHg", minimum=10, maximum=200, variable="dbp"),
        age_input(),
    ),
    compute=compute,
    references=("Lim WS et al. Thorax 2003;58:377-82.",),
))
