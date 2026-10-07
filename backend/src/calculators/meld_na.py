"""MELD-Na — 말기 간질환 중증도 (UNOS/OPTN 2016 정책 식).

MELD(i) = 0.957·ln(Cr) + 0.378·ln(bilirubin) + 1.120·ln(INR) + 0.643 → 소수 첫째 자리로 반올림 후 ×10
  (각 값 <1 → 1, Cr >4 → 4, 지난 7일 투석 ≥2회 또는 24h CVVHD → Cr 4)
MELD(i) >11 이면 MELD = MELD(i) + 1.32·(137 − Na) − 0.033·MELD(i)·(137 − Na), Na 는 125–137 로 제한.
최종 정수 반올림, 6–40.  Kamath PS et al. Hepatology 2001;33:464-70; Kim WR et al. NEJM 2008;359:1018-26.
"""

from __future__ import annotations

import math

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register

MORTALITY_90D = ((9, "≈1.9%"), (19, "≈6.0%"), (29, "≈19.6%"), (39, "≈52.6%"), (40, "≈71.3%"))


def meld_i(creatinine: float, bilirubin: float, inr: float, dialysis: bool) -> int:
    cr = 4.0 if dialysis else min(max(creatinine, 1.0), 4.0)
    bili = max(bilirubin, 1.0)
    inr = max(inr, 1.0)
    raw = 0.957 * math.log(cr) + 0.378 * math.log(bili) + 1.120 * math.log(inr) + 0.643
    return int(round(round(raw, 1) * 10))


def meld_na(creatinine: float, bilirubin: float, inr: float, sodium: float, dialysis: bool) -> tuple[int, int]:
    mi = meld_i(creatinine, bilirubin, inr, dialysis)
    score = float(mi)
    if mi > 11:
        na = min(max(sodium, 125.0), 137.0)
        score = mi + 1.32 * (137 - na) - 0.033 * mi * (137 - na)
    final = int(round(score))
    return max(6, min(40, final)), mi


def compute(i: dict) -> Result:
    score, mi = meld_na(i["creatinine"], i["bilirubin_total"], i["inr"], i["sodium"], i["dialysis"])
    for cut, mort in MORTALITY_90D:
        if score <= cut:
            break
    if score < 10:
        label, sev = "낮음", "ok"
    elif score < 20:
        label, sev = "중간", "warn"
    elif score < 30:
        label, sev = "높음", "danger"
    else:
        label, sev = "매우 높음", "danger"
    notes = [f"3개월 사망률 참고 {mort} (Wiesner 2003 MELD 구간).",
             "Cr >4 또는 투석은 4 로, 각 값 <1 은 1 로 제한하며 Na 는 125–137 로 제한합니다 (UNOS 2016)."]
    if mi <= 11:
        notes.append("MELD(i) ≤11 이라 나트륨 보정을 적용하지 않습니다.")
    return Result(
        value=score, unit="점", label=f"MELD-Na {score} — 사망 위험 {label}", severity=sev,
        details=[
            Detail("크레아티닌", f"{i['creatinine']:g} mg/dL" + (" (투석 → 4.0 적용)" if i["dialysis"] else "")),
            Detail("총 빌리루빈", f"{i['bilirubin_total']:g} mg/dL"),
            Detail("INR", f"{i['inr']:g}"),
            Detail("나트륨", f"{i['sodium']:g} mmol/L"),
            Detail("MELD(i)", str(mi)),
        ],
        notes=notes, extra={"meld_i": mi},
    )


SPEC = register(CalculatorSpec(
    id="meld_na", name="MELD-Na", group="간",
    description="말기 간질환 중증도 평가 (이식 대기 순위 식)",
    inputs=(
        InputSpec("creatinine", "혈청 크레아티닌", "number", unit="mg/dL", minimum=0.1, maximum=50, variable="creatinine"),
        InputSpec("bilirubin_total", "총 빌리루빈", "number", unit="mg/dL", minimum=0, maximum=100, variable="bilirubin_total"),
        InputSpec("inr", "INR", "number", minimum=0.5, maximum=20, variable="inr"),
        InputSpec("sodium", "나트륨", "number", unit="mmol/L", minimum=100, maximum=180, variable="sodium"),
        InputSpec("dialysis", "지난 7일 투석 ≥2회 또는 24시간 CVVHD", "boolean", default=False),
    ),
    compute=compute,
    references=("OPTN Policy 9.1 (2016) MELD calculation.", "Kim WR et al. NEJM 2008;359:1018-26."),
    scale=Scale(6, 40, (Band(10, "낮음", "ok"), Band(20, "중간", "warn"), Band(30, "높음", "danger"), Band(None, "매우 높음", "danger"))),
    guide="말기 간질환의 3개월 사망 위험. 간이식 대기 순위에 쓰는 UNOS 식이며 나트륨 보정이 포함됩니다.",
))
