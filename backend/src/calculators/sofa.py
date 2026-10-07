"""SOFA - Sequential Organ Failure Assessment (Vincent JL et al. Intensive Care Med 1996;22:707-10).

호흡 PaO₂/FiO₂: ≥400 0 · <400 1 · <300 2 · <200 + 호흡 보조 3 · <100 + 호흡 보조 4
응고 혈소판(×10³/µL): ≥150 0 · <150 1 · <100 2 · <50 3 · <20 4
간 빌리루빈(mg/dL): <1.2 0 · 1.2-1.9 1 · 2.0-5.9 2 · 6.0-11.9 3 · ≥12 4
심혈관: MAP ≥70 0 · MAP <70 1 · dopamine ≤5 또는 dobutamine 2 · dopamine >5 또는 epi/norepi ≤0.1 3 ·
        dopamine >15 또는 epi/norepi >0.1 4  (µg/kg/min, ≥1시간)
중추신경 GCS: 15 0 · 13-14 1 · 10-12 2 · 6-9 3 · <6 4
신장 Cr(mg/dL): <1.2 0 · 1.2-1.9 1 · 2.0-3.4 2 · 3.5-4.9 또는 소변량 <500 mL/일 3 · ≥5.0 또는 <200 4
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, INF, InputSpec, Option, Result, Scale, band, register
from src.calculators.common import derive_map

VASOPRESSOR = (
    Option("none", "없음"),
    Option("dopamine_le5_or_dobutamine", "Dopamine ≤5 또는 dobutamine (모든 용량)"),
    Option("dopamine_gt5_or_epi_le0_1", "Dopamine >5 또는 epi/norepi ≤0.1"),
    Option("dopamine_gt15_or_epi_gt0_1", "Dopamine >15 또는 epi/norepi >0.1"),
)
VASO_PTS = {"none": 0, "dopamine_le5_or_dobutamine": 2, "dopamine_gt5_or_epi_le0_1": 3, "dopamine_gt15_or_epi_gt0_1": 4}

MORTALITY = ((6, "<10%"), (9, "15-20%"), (12, "40-50%"), (14, "50-60%"), (15, ">80%"), (24, ">90%"))


def normalize_fio2(fio2: float) -> float:
    """0.21-1.0 분율. 1 초과(퍼센트 입력)는 /100."""
    return fio2 / 100 if fio2 > 1 else fio2


def respiration(pao2: float, fio2: float, ventilated: bool) -> tuple[int, float]:
    pf = pao2 / normalize_fio2(fio2)
    if pf >= 400:
        pts = 0
    elif pf >= 300:
        pts = 1
    elif pf >= 200:
        pts = 2
    elif pf >= 100:
        pts = 3 if ventilated else 2
    else:
        pts = 4 if ventilated else 2
    return pts, pf


def coagulation(platelets: float) -> int:
    return int(band(platelets, [(150, INF, 0), (100, 150, 1), (50, 100, 2), (20, 50, 3), (-INF, 20, 4)]))


def liver(bilirubin: float) -> int:
    return int(band(bilirubin, [(-INF, 1.2, 0), (1.2, 2.0, 1), (2.0, 6.0, 2), (6.0, 12.0, 3), (12.0, INF, 4)]))


def cardiovascular(map_: float, vasopressor: str) -> int:
    v = VASO_PTS[vasopressor]
    if v:
        return v
    return 0 if map_ >= 70 else 1


def cns(gcs: float) -> int:
    return int(band(gcs, [(15, INF, 0), (13, 15, 1), (10, 13, 2), (6, 10, 3), (-INF, 6, 4)]))


def renal(creatinine: float, urine_output_24h: float | None) -> int:
    pts = int(band(creatinine, [(-INF, 1.2, 0), (1.2, 2.0, 1), (2.0, 3.5, 2), (3.5, 5.0, 3), (5.0, INF, 4)]))
    if urine_output_24h is not None:
        if urine_output_24h < 200:
            pts = max(pts, 4)
        elif urine_output_24h < 500:
            pts = max(pts, 3)
    return pts


def compute(i: dict) -> Result:
    resp, pf = respiration(i["pao2"], i["fio2"], i["mechanical_ventilation"])
    sub = {
        "respiration": resp,
        "coagulation": coagulation(i["platelets"]),
        "liver": liver(i["bilirubin_total"]),
        "cardiovascular": cardiovascular(i["map"], i["vasopressor"]),
        "cns": cns(i["gcs"]),
        "renal": renal(i["creatinine"], i.get("urine_output_24h")),
    }
    total = sum(sub.values())
    for cut, mort in MORTALITY:
        if total <= cut:
            break
    if total <= 6:
        label, sev = "경증 장기부전", "ok" if total <= 2 else "warn"
    elif total <= 11:
        label, sev = "중등도 장기부전", "warn"
    else:
        label, sev = "중증 다장기부전", "danger"
    vaso_label = next(o.label for o in VASOPRESSOR if o.value == i["vasopressor"])
    uo = i.get("urine_output_24h")
    return Result(
        value=total, unit="점", label=label, severity=sev,
        details=[
            Detail("호흡 (PaO₂/FiO₂)", f"{pf:.0f}" + (" · 호흡 보조" if i["mechanical_ventilation"] else ""), sub["respiration"]),
            Detail("응고 (혈소판)", f"{i['platelets']:g} ×10³/µL", sub["coagulation"]),
            Detail("간 (빌리루빈)", f"{i['bilirubin_total']:g} mg/dL", sub["liver"]),
            Detail("심혈관", f"MAP {i['map']:g} mmHg · {vaso_label}", sub["cardiovascular"]),
            Detail("중추신경 (GCS)", f"{i['gcs']:g}", sub["cns"]),
            Detail("신장", f"Cr {i['creatinine']:g} mg/dL" + (f" · 소변량 {uo:g} mL/일" if uo is not None else ""), sub["renal"]),
        ],
        notes=[f"ICU 사망률 참고 {mort} (Vincent 1998 최대 SOFA).",
               "Sepsis-3: 기저치 대비 SOFA ≥2점 상승이 장기부전 기준입니다. 24시간 중 최악값으로 매깁니다."],
        extra={"subscores": sub, "pf_ratio": round(pf, 1)},
    )


SPEC = register(CalculatorSpec(
    id="sofa", name="SOFA", group="중증도",
    description="장기 기능부전 / 중증도 평가",
    inputs=(
        InputSpec("pao2", "PaO₂", "number", unit="mmHg", minimum=10, maximum=700, variable="pao2"),
        InputSpec("fio2", "FiO₂", "number", unit="분율(0.21-1.0)", minimum=0.21, maximum=100, variable="fio2",
                  help="퍼센트로 입력해도 됩니다 (예: 40 → 0.40)"),
        InputSpec("mechanical_ventilation", "기계환기 / 호흡 보조 중", "boolean", default=False),
        InputSpec("platelets", "혈소판", "number", unit="×10³/µL", minimum=0, maximum=3000, variable="platelets"),
        InputSpec("bilirubin_total", "총 빌리루빈", "number", unit="mg/dL", minimum=0, maximum=100, variable="bilirubin_total"),
        InputSpec("map", "평균동맥압 (MAP)", "number", unit="mmHg", minimum=10, maximum=250, derive=derive_map,
                  help="기록이 없으면 (SBP + 2·DBP)/3 로 채움"),
        InputSpec("vasopressor", "혈압상승제 (µg/kg/min, ≥1시간)", "select", default="none", options=VASOPRESSOR),
        InputSpec("gcs", "GCS", "number", minimum=3, maximum=15, variable="gcs"),
        InputSpec("creatinine", "혈청 크레아티닌", "number", unit="mg/dL", minimum=0.1, maximum=50, variable="creatinine"),
        InputSpec("urine_output_24h", "24시간 소변량", "number", unit="mL/일", minimum=0, maximum=20000, required=False,
                  variable="urine_output_24h"),
    ),
    compute=compute,
    references=("Vincent JL et al. Intensive Care Med 1996;22:707-10.", "Singer M et al. JAMA 2016;315:801-10 (Sepsis-3)."),
    scale=Scale(0, 24, (Band(3, "경증", "ok"), Band(7, "경증~중등도", "warn"), Band(12, "중등도", "warn"), Band(None, "중증", "danger"))),
    guide="호흡·응고·간·심혈관·중추신경·신장 6개 장기를 각 0~4점으로. 패혈증(Sepsis-3)은 기저치 대비 2점 이상 상승으로 정의합니다.",
))
