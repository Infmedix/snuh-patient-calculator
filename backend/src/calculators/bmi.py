"""BMI - 체질량지수. 분류는 대한비만학회 비만 진료지침 2022 (아시아·태평양 기준).

저체중 <18.5 / 정상 18.5-22.9 / 비만전단계(과체중) 23-24.9 / 1단계 비만 25-29.9 / 2단계 30-34.9 / 3단계 ≥35.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register


def compute(i: dict) -> Result:
    h = i["height_cm"] / 100
    bmi = i["weight_kg"] / (h * h)
    if bmi < 18.5:
        label, sev = "저체중", "warn"
    elif bmi < 23:
        label, sev = "정상", "ok"
    elif bmi < 25:
        label, sev = "비만전단계", "info"
    elif bmi < 30:
        label, sev = "1단계 비만", "warn"
    elif bmi < 35:
        label, sev = "2단계 비만", "danger"
    else:
        label, sev = "3단계 비만", "danger"
    return Result(
        value=round(bmi, 1), unit="kg/m²", label=label, severity=sev,
        details=[Detail("체중", f"{i['weight_kg']:g} kg"), Detail("신장", f"{i['height_cm']:g} cm")],
        notes=["분류: 대한비만학회 2022 (아시아·태평양 기준). 근육량이 많거나 부종이 있으면 과대평가될 수 있습니다."],
    )


SPEC = register(CalculatorSpec(
    id="bmi", name="BMI", group="신체·신장",
    description="체질량지수 - 비만/체중 상태 평가",
    inputs=(
        InputSpec("weight_kg", "체중", "number", unit="kg", minimum=1, maximum=500, variable="weight_kg"),
        InputSpec("height_cm", "신장", "number", unit="cm", minimum=30, maximum=300, variable="height_cm"),
    ),
    compute=compute,
    references=("대한비만학회. 비만 진료지침 2022.",),
    scale=Scale(10, 45, (Band(18.5, "저체중", "warn"), Band(23, "정상", "ok"), Band(25, "비만전단계", "info"),
                         Band(30, "1단계 비만", "warn"), Band(35, "2단계 비만", "danger"), Band(None, "3단계 비만", "danger"))),
    guide="체중(kg)을 신장(m)의 제곱으로 나눈 값. 한국인 기준(대한비만학회)은 23 이상을 비만전단계, 25 이상을 비만으로 봅니다.",
))
