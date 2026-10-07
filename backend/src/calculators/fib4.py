"""FIB-4 - 간섬유화 비침습 지표. Sterling RK et al. Hepatology 2006;43:1317-25.

FIB-4 = 나이 × AST / (혈소판(×10³/µL) × √ALT)
<1.3 진행 섬유화 가능성 낮음 · 1.3-2.67 중간(추가 검사) · >2.67 진행 섬유화(F3-4) 가능성 높음.
65세 이상은 하한을 2.0 으로 올린다 (McPherson S et al. Am J Gastroenterol 2017).
"""

from __future__ import annotations

import math

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register
from src.calculators.common import age_input


def fib4(age: float, ast: float, alt: float, platelets: float) -> float:
    return age * ast / (platelets * math.sqrt(alt))


def compute(i: dict) -> Result:
    v = fib4(i["age"], i["ast"], i["alt"], i["platelets"])
    low_cut = 2.0 if i["age"] >= 65 else 1.3
    if v < low_cut:
        label, sev = f"낮음 (<{low_cut:g}) - 진행 섬유화 가능성 낮음", "ok"
    elif v <= 2.67:
        label, sev = "중간 (1.3-2.67) - 탄성도 검사 등 추가 평가", "warn"
    else:
        label, sev = "높음 (>2.67) - 진행 섬유화(F3-4) 가능성", "danger"
    return Result(
        value=round(v, 2), label=label, severity=sev,
        details=[Detail("나이", f"{i['age']:g}세"), Detail("AST", f"{i['ast']:g} U/L"), Detail("ALT", f"{i['alt']:g} U/L"),
                 Detail("혈소판", f"{i['platelets']:g} ×10³/µL")],
        notes=["만성 간질환(특히 NAFLD·HCV)의 진행 섬유화 선별용. 급성 간염·근육 손상 등 일시적 간효소 상승에서는 신뢰할 수 없습니다.",
               "65세 이상은 하한 2.0 적용 (McPherson 2017)."],
    )


SPEC = register(CalculatorSpec(
    id="fib4", name="FIB-4", group="간",
    description="간섬유화 비침습 지표",
    inputs=(
        age_input(),
        InputSpec("ast", "AST", "number", unit="U/L", minimum=1, maximum=10000, variable="ast"),
        InputSpec("alt", "ALT", "number", unit="U/L", minimum=1, maximum=10000, variable="alt"),
        InputSpec("platelets", "혈소판", "number", unit="×10³/µL", minimum=1, maximum=3000, variable="platelets"),
    ),
    compute=compute,
    references=("Sterling RK et al. Hepatology 2006;43:1317-25.", "McPherson S et al. Am J Gastroenterol 2017;112:740-51."),
    scale=Scale(0, 6, (Band(1.3, "낮음", "ok"), Band(2.67, "중간", "warn"), Band(None, "높음", "danger")),
                note="65세 이상은 하한 2.0."),
    guide="나이·AST·ALT·혈소판만으로 진행 간섬유화 가능성을 가르는 지표. 1.3 미만이면 배제, 2.67 초과면 탄성도 검사나 전문의 의뢰를 고려합니다.",
))
