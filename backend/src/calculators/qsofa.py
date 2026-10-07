"""qSOFA - quick SOFA (Sepsis-3 병동 선별). Singer M et al. JAMA 2016;315:801-10.

호흡수 ≥22/분 1점, 수축기 혈압 ≤100 mmHg 1점, 의식 변화(GCS <15) 1점. 0-3점. 2점 이상이면 패혈증 의심 → 장기부전(SOFA) 평가.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register


def compute(i: dict) -> Result:
    items = [
        ("호흡수 ≥22/분", i["rr"] >= 22, f"{i['rr']:g}/분"),
        ("수축기 혈압 ≤100 mmHg", i["sbp"] <= 100, f"{i['sbp']:g} mmHg"),
        ("의식 변화 (GCS <15)", i["gcs"] < 15, f"GCS {i['gcs']:g}"),
    ]
    details = [Detail(l, t, 1 if c else 0) for l, c, t in items]
    score = sum(1 for _, c, _ in items if c)
    if score >= 2:
        label, sev = "패혈증 의심 - SOFA·젖산 평가, 감염 치료 검토", "danger"
    elif score == 1:
        label, sev = "경계 - 재평가", "warn"
    else:
        label, sev = "저위험", "ok"
    return Result(value=score, unit="점", label=label, severity=sev, details=details,
                  notes=["감염이 의심되는 환자에서 ICU 밖(병동·응급실) 선별용. 2점 미만이어도 패혈증을 배제하지 않습니다 (Sepsis-3).",
                         "확정 평가는 SOFA 2점 이상 상승입니다."])


SPEC = register(CalculatorSpec(
    id="qsofa", name="qSOFA", group="조기경고",
    description="병동·응급실 패혈증 빠른 선별",
    inputs=(
        InputSpec("rr", "호흡수", "number", unit="/분", minimum=0, maximum=100, variable="rr"),
        InputSpec("sbp", "수축기 혈압", "number", unit="mmHg", minimum=20, maximum=300, variable="sbp"),
        InputSpec("gcs", "GCS", "number", minimum=3, maximum=15, variable="gcs"),
    ),
    compute=compute,
    references=("Singer M et al. JAMA 2016;315:801-10 (Sepsis-3).",),
    scale=Scale(0, 3, (Band(1, "저위험", "ok"), Band(2, "경계", "warn"), Band(None, "패혈증 의심", "danger"))),
    guide="감염이 의심될 때 활력징후 둘과 의식만으로 패혈증 위험을 빠르게 거릅니다. 2점 이상이면 SOFA 로 장기부전을 평가합니다.",
))
