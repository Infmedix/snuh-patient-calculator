"""CHA₂DS₂-VASc — 심방세동 환자의 뇌졸중/전신 혈전색전증 위험.

C 심부전/좌심실 기능저하 1, H 고혈압 1, A₂ ≥75세 2, D 당뇨 1, S₂ 뇌졸중/TIA/혈전색전증 2,
V 혈관질환(심근경색·말초동맥질환·대동맥판) 1, A 65–74세 1, Sc 여성 1.  Lip GYH et al. Chest 2010;137:263-72.
연간 뇌졸중/TE 위험(참고): Friberg L et al. Eur Heart J 2012;33:1500-10.
"""

from __future__ import annotations

from src.calculators.base import CalculatorSpec, Detail, Result, register
from src.calculators.common import age_input, flag_input, sex_input

ANNUAL_RISK = {0: 0.2, 1: 0.6, 2: 2.2, 3: 3.2, 4: 4.8, 5: 7.2, 6: 9.7, 7: 11.2, 8: 10.8, 9: 12.2}


def compute(i: dict) -> Result:
    details = []

    def add(label, cond, pts):
        details.append(Detail(label, "예" if cond else "아니오", pts if cond else 0))
        return pts if cond else 0

    score = 0
    score += add("심부전 / 좌심실 기능저하 (C)", i["heart_failure"], 1)
    score += add("고혈압 (H)", i["hypertension"], 1)
    age = i["age"]
    score += add("나이 ≥75 (A₂)", age >= 75, 2)
    score += add("당뇨 (D)", i["diabetes"], 1)
    score += add("뇌졸중 / TIA / 혈전색전증 (S₂)", i["stroke_tia"], 2)
    score += add("혈관질환 (V)", i["vascular_disease"], 1)
    score += add("나이 65–74 (A)", 65 <= age < 75, 1)
    female = i["sex"] == "F"
    score += add("여성 (Sc)", female, 1)

    # 성별 제외 점수로 해석 (ESC 2020: 남 0 / 여 1 = 저위험, 남 1 / 여 2 = 항응고 고려, 그 이상 권고)
    non_sex = score - (1 if female else 0)
    if non_sex == 0:
        label, sev = "저위험 — 항응고 치료 불필요", "ok"
    elif non_sex == 1:
        label, sev = "중간 — 항응고 치료 고려", "warn"
    else:
        label, sev = "고위험 — 항응고 치료 권고", "danger"
    notes = [f"연간 뇌졸중/TE 위험 약 {ANNUAL_RISK[score]}% (Friberg 2012, 참고용).",
             "비판막성 심방세동 환자에 적용. 여성 단독 1점은 위험 인자로 세지 않습니다 (ESC 2020)."]
    return Result(value=score, unit="점", label=label, severity=sev, details=details, notes=notes)


SPEC = register(CalculatorSpec(
    id="cha2ds2_vasc", name="CHA₂DS₂-VASc", group="심혈관",
    description="심방세동 환자의 뇌졸중 위험 평가",
    inputs=(
        age_input(),
        sex_input(),
        flag_input("heart_failure", "심부전 / 좌심실 기능저하", "heart_failure"),
        flag_input("hypertension", "고혈압", "hypertension"),
        flag_input("diabetes", "당뇨", "diabetes"),
        flag_input("stroke_tia", "뇌졸중 / TIA / 혈전색전증 병력", "stroke_tia"),
        flag_input("vascular_disease", "혈관질환 (심근경색·말초동맥질환·대동맥판)", "vascular_disease"),
    ),
    compute=compute,
    references=("Lip GYH et al. Chest 2010;137:263-72.", "Hindricks G et al. ESC 2020 AF Guidelines."),
))
