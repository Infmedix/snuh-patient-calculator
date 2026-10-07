"""Charlson 동반질환지수 (나이 보정). Charlson ME et al. J Chronic Dis 1987;40:373-83.
ICD-10 매핑은 Quan H et al. Med Care 2005;43:1130-9 (src/snapshot/flags.py 의 CHARLSON 표).

가중치: 심근경색 1 · 심부전 1 · 말초혈관질환 1 · 뇌혈관질환 1 · 치매 1 · 만성 폐질환 1 · 결합조직질환 1 · 소화성궤양 1 ·
경증 간질환 1 · 당뇨(합병증 없음) 1 · 당뇨(합병증) 2 · 편마비 2 · 중등도 이상 신질환 2 · 악성종양(백혈병·림프종 포함) 2 ·
중등도-중증 간질환 3 · 전이성 고형암 6 · AIDS 6.  나이: 50-59 +1 · 60-69 +2 · 70-79 +3 · ≥80 +4.
같은 축의 상위 항목이 있으면 하위는 세지 않는다 (당뇨 합병증 > 당뇨, 중증 간질환 > 경증, 전이암 > 악성종양).
10년 생존 추정 = 0.983^(e^(0.9×점수)) (원 논문의 나이 보정 공식).
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register
from src.calculators.common import age_input

# (키, 라벨, 가중치) - flag 이름은 "cci_" + 키
ITEMS = (
    ("mi", "심근경색", 1),
    ("chf", "울혈성 심부전", 1),
    ("pvd", "말초혈관질환", 1),
    ("cerebrovascular", "뇌혈관질환", 1),
    ("dementia", "치매", 1),
    ("copd", "만성 폐질환", 1),
    ("rheumatic", "결합조직질환(류마티스)", 1),
    ("pud", "소화성 궤양", 1),
    ("mild_liver", "경증 간질환", 1),
    ("diabetes", "당뇨 (합병증 없음)", 1),
    ("diabetes_complicated", "당뇨 (만성 합병증)", 2),
    ("hemiplegia", "편마비·하반신마비", 2),
    ("renal", "중등도 이상 신질환", 2),
    ("malignancy", "악성종양 (백혈병·림프종 포함)", 2),
    ("severe_liver", "중등도-중증 간질환", 3),
    ("metastatic", "전이성 고형암", 6),
    ("aids", "AIDS", 6),
)
# 상위 항목이 있으면 세지 않는 하위 항목
SUPERSEDES = {"diabetes_complicated": "diabetes", "severe_liver": "mild_liver", "metastatic": "malignancy"}


def age_points(age: float) -> int:
    if age >= 80:
        return 4
    if age >= 70:
        return 3
    if age >= 60:
        return 2
    if age >= 50:
        return 1
    return 0


def compute(i: dict) -> Result:
    present = {k for k, _, _ in ITEMS if i[k]}
    counted = set(present)
    for upper, lower in SUPERSEDES.items():
        if upper in present:
            counted.discard(lower)
    details = []
    score = 0
    for k, label, w in ITEMS:
        if k in counted:
            details.append(Detail(label, "예", w))
            score += w
        elif k in present:
            details.append(Detail(label, "예 (상위 항목에 포함)", 0))
    ap = age_points(i["age"])
    details.append(Detail("나이", f"{i['age']:g}세", ap))
    total = score + ap
    survival = 0.983 ** (2.718281828 ** (0.9 * total)) * 100
    if total <= 1:
        label, sev = "낮음", "ok"
    elif total <= 3:
        label, sev = "중간", "warn"
    else:
        label, sev = "높음", "danger"
    return Result(
        value=total, unit="점", label=f"동반질환 부담 {label}", severity=sev, details=details,
        notes=[f"10년 생존 추정 약 {survival:.0f}% (원 논문 공식, 참고용 - 현대 치료 성적과는 차이가 있습니다).",
               "자동 체크는 최근 진단 코드(Quan 2005 ICD-10 매핑)에서 제안한 것입니다. 진단 코드가 없는 병력은 직접 체크하세요."],
        extra={"comorbidity_points": score, "age_points": ap, "survival_10y_pct": round(survival, 1)},
    )


def _inputs():
    out = [age_input()]
    for k, label, w in ITEMS:
        out.append(InputSpec(k, f"{label} ({w}점)", "boolean", default=False, flag=f"cci_{k}"))
    return tuple(out)


SPEC = register(CalculatorSpec(
    id="charlson", name="Charlson 동반질환지수", group="동반질환",
    description="동반질환 부담과 장기 예후 (나이 보정)",
    inputs=_inputs(),
    compute=compute,
    references=("Charlson ME et al. J Chronic Dis 1987;40:373-83.", "Quan H et al. Med Care 2005;43:1130-9."),
    scale=Scale(0, 12, (Band(2, "낮음", "ok"), Band(4, "중간", "warn"), Band(None, "높음", "danger"))),
    guide="17개 동반질환에 가중치를 주고 나이를 더한 점수. 진단 코드로 자동 제안되며, 연구·예후 설명·수술 전 평가에 씁니다.",
))
