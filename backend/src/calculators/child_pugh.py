"""Child-Pugh — 간경변 중증도.

빌리루빈 <2 / 2–3 / >3 mg/dL → 1/2/3, 알부민 >3.5 / 2.8–3.5 / <2.8 g/dL → 1/2/3,
INR <1.7 / 1.7–2.3 / >2.3 → 1/2/3, 복수 없음/경도(이뇨제 조절)/중등도 이상 → 1/2/3,
뇌병증 없음/1–2등급/3–4등급 → 1/2/3.  Class A 5–6, B 7–9, C 10–15.  Pugh RNH et al. Br J Surg 1973;60:646-9.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Option, Result, Scale, register


def _pts(value, cuts, ascending=True):
    """cuts = (lo, hi): ascending → <lo 1, lo–hi 2, >hi 3; descending(알부민) → >hi 1, lo–hi 2, <lo 3."""
    lo, hi = cuts
    if ascending:
        return 1 if value < lo else (2 if value <= hi else 3)
    return 1 if value > hi else (2 if value >= lo else 3)


SELECT_PTS = {"none": 1, "mild": 2, "moderate_severe": 3, "grade_1_2": 2, "grade_3_4": 3}
ASCITES_LABEL = {"none": "없음", "mild": "경도 (이뇨제로 조절)", "moderate_severe": "중등도 이상 (난치성)"}
ENCEPH_LABEL = {"none": "없음", "grade_1_2": "1–2등급", "grade_3_4": "3–4등급"}


def compute(i: dict) -> Result:
    b = _pts(i["bilirubin_total"], (2, 3))
    a = _pts(i["albumin"], (2.8, 3.5), ascending=False)
    n = _pts(i["inr"], (1.7, 2.3))
    asc = SELECT_PTS[i["ascites"]]
    enc = SELECT_PTS[i["encephalopathy"]]
    score = b + a + n + asc + enc
    if score <= 6:
        label, sev, surv = "Class A — 잘 보존된 간기능", "ok", "1년 생존 ~100%, 2년 ~85%"
    elif score <= 9:
        label, sev, surv = "Class B — 유의한 기능 저하", "warn", "1년 생존 ~80%, 2년 ~60%"
    else:
        label, sev, surv = "Class C — 비대상성 간경변", "danger", "1년 생존 ~45%, 2년 ~35%"
    return Result(
        value=score, unit="점", label=label, severity=sev,
        details=[
            Detail("총 빌리루빈", f"{i['bilirubin_total']:g} mg/dL", b),
            Detail("알부민", f"{i['albumin']:g} g/dL", a),
            Detail("INR", f"{i['inr']:g}", n),
            Detail("복수", ASCITES_LABEL[i["ascites"]], asc),
            Detail("간성뇌병증", ENCEPH_LABEL[i["encephalopathy"]], enc),
        ],
        notes=[f"참고 생존율: {surv} (수술 위험 평가 문헌 기준).", "복수·뇌병증은 진찰 소견이라 직접 입력합니다."],
    )


SPEC = register(CalculatorSpec(
    id="child_pugh", name="Child-Pugh", group="간",
    description="간경변 중증도 / 간기능 평가",
    inputs=(
        InputSpec("bilirubin_total", "총 빌리루빈", "number", unit="mg/dL", minimum=0, maximum=100, variable="bilirubin_total"),
        InputSpec("albumin", "알부민", "number", unit="g/dL", minimum=0.5, maximum=8, variable="albumin"),
        InputSpec("inr", "INR", "number", minimum=0.5, maximum=20, variable="inr"),
        InputSpec("ascites", "복수", "select", default="none",
                  options=tuple(Option(k, v) for k, v in ASCITES_LABEL.items())),
        InputSpec("encephalopathy", "간성뇌병증", "select", default="none",
                  options=tuple(Option(k, v) for k, v in ENCEPH_LABEL.items())),
    ),
    compute=compute,
    references=("Pugh RNH et al. Br J Surg 1973;60:646-9.",),
    scale=Scale(5, 15, (Band(7, "Class A", "ok"), Band(10, "Class B", "warn"), Band(None, "Class C", "danger"))),
    guide="간경변의 중증도를 검사 3가지와 진찰 소견 2가지로 5~15점으로 매깁니다. 복수·뇌병증은 기록에서 가져올 수 없어 직접 고릅니다.",
))
