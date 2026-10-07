"""APACHE II — 중환자 중증도 (Knaus WA et al. Crit Care Med 1985;13:818-29).

APS 12항목(입실 후 24시간 최악값) + 나이 점수 + 만성 건강 점수. 0–71.
산소화: FiO₂ ≥0.5 → A-aDO₂ = FiO₂·713 − PaCO₂/0.8 − PaO₂ (≥500 4 · 350–499 3 · 200–349 2 · <200 0),
        FiO₂ <0.5 → PaO₂ (>70 0 · 61–70 1 · 55–60 3 · <55 4).
산염기: 동맥혈 pH 우선, ABG 없으면 HCO₃⁻. 크레아티닌: 급성 신부전이면 점수 2배. GCS: 15 − GCS.
나이: ≤44 0 · 45–54 2 · 55–64 3 · 65–74 5 · ≥75 6.
만성 건강(중증 장기부전·면역저하 병력): 비수술/응급수술 5 · 선택수술 2.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, INF, InputError, InputSpec, Option, Result, Scale, band, register
from src.calculators.common import age_input, derive_map
from src.calculators.sofa import normalize_fio2

T = [(41, INF, 4), (39, 41, 3), (38.5, 39, 1), (36, 38.5, 0), (34, 36, 1), (32, 34, 2), (30, 32, 3), (-INF, 30, 4)]
MAP = [(160, INF, 4), (130, 160, 3), (110, 130, 2), (70, 110, 0), (50, 70, 2), (-INF, 50, 4)]
HR = [(180, INF, 4), (140, 180, 3), (110, 140, 2), (70, 110, 0), (55, 70, 2), (40, 55, 3), (-INF, 40, 4)]
RR = [(50, INF, 4), (35, 50, 3), (25, 35, 1), (12, 25, 0), (10, 12, 1), (6, 10, 2), (-INF, 6, 4)]
AADO2 = [(500, INF, 4), (350, 500, 3), (200, 350, 2), (-INF, 200, 0)]
PAO2 = [(70, INF, 0), (61, 70, 1), (55, 61, 3), (-INF, 55, 4)]
PH = [(7.7, INF, 4), (7.6, 7.7, 3), (7.5, 7.6, 1), (7.33, 7.5, 0), (7.25, 7.33, 2), (7.15, 7.25, 3), (-INF, 7.15, 4)]
HCO3 = [(52, INF, 4), (41, 52, 3), (32, 41, 1), (22, 32, 0), (18, 22, 2), (15, 18, 3), (-INF, 15, 4)]
NA = [(180, INF, 4), (160, 180, 3), (155, 160, 2), (150, 155, 1), (130, 150, 0), (120, 130, 2), (111, 120, 3), (-INF, 111, 4)]
K = [(7, INF, 4), (6, 7, 3), (5.5, 6, 1), (3.5, 5.5, 0), (3, 3.5, 1), (2.5, 3, 2), (-INF, 2.5, 4)]
CR = [(3.5, INF, 4), (2, 3.5, 3), (1.5, 2, 2), (0.6, 1.5, 0), (-INF, 0.6, 2)]
HCT = [(60, INF, 4), (50, 60, 2), (46, 50, 1), (30, 46, 0), (20, 30, 2), (-INF, 20, 4)]
WBC = [(40, INF, 4), (20, 40, 2), (15, 20, 1), (3, 15, 0), (1, 3, 2), (-INF, 1, 4)]
AGE = [(75, INF, 6), (65, 75, 5), (55, 65, 3), (45, 55, 2), (-INF, 45, 0)]
CHRONIC = {"none": 0, "nonoperative_or_emergency_postop": 5, "elective_postop": 2}
CHRONIC_OPTIONS = (
    Option("none", "해당 없음"),
    Option("nonoperative_or_emergency_postop", "중증 만성질환 + 비수술 또는 응급수술 환자"),
    Option("elective_postop", "중증 만성질환 + 선택수술 환자"),
)
MORTALITY = ((4, "≈4%"), (9, "≈8%"), (14, "≈15%"), (19, "≈25%"), (24, "≈40%"), (29, "≈55%"), (34, "≈75%"), (71, "≈85%"))


def oxygenation(fio2: float, pao2: float, paco2: float | None) -> tuple[int, str]:
    f = normalize_fio2(fio2)
    if f >= 0.5:
        if paco2 is None:
            raise InputError("FiO₂ ≥0.5 에서는 A-aDO₂ 계산에 PaCO₂ 가 필요합니다", missing=["paco2"])
        aado2 = f * 713 - paco2 / 0.8 - pao2
        return int(band(aado2, AADO2)), f"A-aDO₂ {aado2:.0f} mmHg (FiO₂ {f:.2f})"
    return int(band(pao2, PAO2)), f"PaO₂ {pao2:g} mmHg (FiO₂ {f:.2f})"


def acid_base(ph: float | None, hco3: float | None) -> tuple[int, str]:
    if ph is not None:
        return int(band(ph, PH)), f"동맥혈 pH {ph:g}"
    if hco3 is not None:
        return int(band(hco3, HCO3)), f"HCO₃⁻ {hco3:g} mmol/L (ABG 없음)"
    raise InputError("동맥혈 pH 또는 HCO₃⁻ 중 하나가 필요합니다", missing=["ph"])


def compute(i: dict) -> Result:
    ox_pts, ox_txt = oxygenation(i["fio2"], i["pao2"], i.get("paco2"))
    ab_pts, ab_txt = acid_base(i.get("ph"), i.get("hco3"))
    cr_pts = int(band(i["creatinine"], CR)) * (2 if i["acute_renal_failure"] else 1)
    aps = {
        "temperature": int(band(i["temp_c"], T)),
        "map": int(band(i["map"], MAP)),
        "hr": int(band(i["hr"], HR)),
        "rr": int(band(i["rr"], RR)),
        "oxygenation": ox_pts,
        "acid_base": ab_pts,
        "sodium": int(band(i["sodium"], NA)),
        "potassium": int(band(i["potassium"], K)),
        "creatinine": cr_pts,
        "hematocrit": int(band(i["hematocrit"], HCT)),
        "wbc": int(band(i["wbc"], WBC)),
        "gcs": int(15 - i["gcs"]),
    }
    age_pts = int(band(i["age"], AGE))
    chronic_pts = CHRONIC[i["chronic_health"]]
    total = sum(aps.values()) + age_pts + chronic_pts
    for cut, mort in MORTALITY:
        if total <= cut:
            break
    if total <= 9:
        label, sev = "낮은 중증도", "ok"
    elif total <= 19:
        label, sev = "중등도", "warn"
    else:
        label, sev = "높은 중증도", "danger"
    details = [
        Detail("체온", f"{i['temp_c']:g} ℃", aps["temperature"]),
        Detail("MAP", f"{i['map']:g} mmHg", aps["map"]),
        Detail("심박수", f"{i['hr']:g}/분", aps["hr"]),
        Detail("호흡수", f"{i['rr']:g}/분", aps["rr"]),
        Detail("산소화", ox_txt, aps["oxygenation"]),
        Detail("산염기", ab_txt, aps["acid_base"]),
        Detail("나트륨", f"{i['sodium']:g} mmol/L", aps["sodium"]),
        Detail("칼륨", f"{i['potassium']:g} mmol/L", aps["potassium"]),
        Detail("크레아티닌", f"{i['creatinine']:g} mg/dL" + (" · 급성 신부전 ×2" if i["acute_renal_failure"] else ""), aps["creatinine"]),
        Detail("헤마토크릿", f"{i['hematocrit']:g} %", aps["hematocrit"]),
        Detail("백혈구", f"{i['wbc']:g} ×10³/µL", aps["wbc"]),
        Detail("GCS", f"{i['gcs']:g} (15 − GCS)", aps["gcs"]),
        Detail("나이", f"{i['age']:g}세", age_pts),
        Detail("만성 건강", next(o.label for o in CHRONIC_OPTIONS if o.value == i["chronic_health"]), chronic_pts),
    ]
    return Result(
        value=total, unit="점", label=label, severity=sev, details=details,
        notes=[f"비수술 환자 병원 사망률 참고 {mort} (Knaus 1985).",
               "입실 후 24시간 동안의 최악값으로 매깁니다. 자동 채움값은 최근 1건이므로 최악값인지 확인하세요."],
        extra={"aps": aps, "age_points": age_pts, "chronic_health_points": chronic_pts},
    )


SPEC = register(CalculatorSpec(
    id="apache2", name="APACHE II", group="중증도",
    description="중환자 중증도 평가 (입실 24시간)",
    inputs=(
        InputSpec("temp_c", "체온", "number", unit="℃", minimum=20, maximum=45, variable="temp_c"),
        InputSpec("map", "평균동맥압 (MAP)", "number", unit="mmHg", minimum=10, maximum=250, derive=derive_map,
                  help="기록이 없으면 (SBP + 2·DBP)/3 로 채움"),
        InputSpec("hr", "심박수", "number", unit="/분", minimum=0, maximum=300, variable="hr"),
        InputSpec("rr", "호흡수", "number", unit="/분", minimum=0, maximum=100, variable="rr"),
        InputSpec("fio2", "FiO₂", "number", unit="분율(0.21–1.0)", minimum=0.21, maximum=100, variable="fio2",
                  help="퍼센트로 입력해도 됩니다"),
        InputSpec("pao2", "PaO₂", "number", unit="mmHg", minimum=10, maximum=700, variable="pao2"),
        InputSpec("paco2", "PaCO₂", "number", unit="mmHg", minimum=5, maximum=200, required=False, variable="paco2",
                  help="FiO₂ ≥0.5 일 때 필요 (A-aDO₂)"),
        InputSpec("ph", "동맥혈 pH", "number", minimum=6.5, maximum=8.0, required=False, variable="ph"),
        InputSpec("hco3", "HCO₃⁻ (ABG 없을 때)", "number", unit="mmol/L", minimum=1, maximum=80, required=False, variable="hco3"),
        InputSpec("sodium", "나트륨", "number", unit="mmol/L", minimum=100, maximum=200, variable="sodium"),
        InputSpec("potassium", "칼륨", "number", unit="mmol/L", minimum=1, maximum=12, variable="potassium"),
        InputSpec("creatinine", "혈청 크레아티닌", "number", unit="mg/dL", minimum=0.1, maximum=50, variable="creatinine"),
        InputSpec("acute_renal_failure", "급성 신부전", "boolean", default=False),
        InputSpec("hematocrit", "헤마토크릿", "number", unit="%", minimum=5, maximum=80, variable="hematocrit"),
        InputSpec("wbc", "백혈구", "number", unit="×10³/µL", minimum=0, maximum=500, variable="wbc"),
        InputSpec("gcs", "GCS", "number", minimum=3, maximum=15, variable="gcs"),
        age_input(),
        InputSpec("chronic_health", "만성 건강 상태", "select", default="none", options=CHRONIC_OPTIONS,
                  help="중증 장기부전(간경변·NYHA IV·만성 호흡부전·투석) 또는 면역저하 병력이 있을 때"),
    ),
    compute=compute,
    references=("Knaus WA et al. Crit Care Med 1985;13:818-29.",),
    scale=Scale(0, 71, (Band(10, "낮음", "ok"), Band(20, "중등도", "warn"), Band(None, "높음", "danger"))),
    guide="중환자실 입실 첫 24시간의 최악값 12항목 + 나이 + 만성질환으로 사망 위험을 추정합니다. 자동 채움은 최근 1건이므로 최악값인지 확인하세요.",
))
