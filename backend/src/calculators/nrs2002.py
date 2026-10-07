"""NRS-2002 - Nutritional Risk Screening (Kondrup J et al. Clin Nutr 2003;22:321-36, ESPEN).

최종 스크리닝 = 영양상태 손상(0-3) + 질병 중증도(0-3) + 70세 이상 1.  ≥3 영양 위험 → 영양 치료 계획.
영양상태: 1 경도 - 3개월 체중감소 >5% 또는 지난주 섭취 50-75%
          2 중등도 - 2개월 체중감소 >5% 또는 BMI 18.5-20.5 + 전신상태 저하 또는 섭취 25-50%
          3 중증 - 1개월 체중감소 >5% (3개월 >15%) 또는 BMI <18.5 + 전신상태 저하 또는 섭취 0-25%
질병 중증도: 1 경도 - 고관절 골절, 급성 합병증 동반 만성질환(간경변·COPD·투석·당뇨·종양)
             2 중등도 - 대복부 수술, 뇌졸중, 중증 폐렴, 혈액암
             3 중증 - 두부 손상, 골수이식, 중환자(APACHE >10)
체중 이력이 있으면 체중감소율·BMI 로 영양상태를 **제안**하고, 섭취량·전신상태는 사용자가 반영한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.calculators.base import Band, CalculatorSpec, Derived, Detail, InputSpec, Option, Result, Scale, register
from src.calculators.common import age_input
from src.snapshot.model import Snapshot

NUTRITION = (Option("absent", "없음 (0)"), Option("mild", "경도 (1)"), Option("moderate", "중등도 (2)"), Option("severe", "중증 (3)"))
SEVERITY = (Option("absent", "없음 (0)"), Option("mild", "경도 (1)"), Option("moderate", "중등도 (2)"), Option("severe", "중증 (3)"))
PTS = {"absent": 0, "mild": 1, "moderate": 2, "severe": 3}


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def weight_loss_pct(history: list, months: int) -> Optional[tuple[float, str]]:
    """최신 체중 대비 약 `months` 개월 전(±15일 창에서 가장 가까운 기록) 체중의 감소율(%). 증가는 음수."""
    if len(history) < 2:
        return None
    latest = history[0]
    t0 = _parse(latest.observed_at)
    if t0 is None:
        return None
    target = months * 30.4
    best = None
    for p in history[1:]:
        t = _parse(p.observed_at)
        if t is None:
            continue
        days = (t0 - t).days
        if abs(days - target) <= 15 and (best is None or abs(days - target) < best[0]):
            best = (abs(days - target), p)
    if best is None:
        return None
    ref = best[1]
    loss = (ref.value - latest.value) / ref.value * 100
    return round(loss, 1), f"{ref.value:g} kg ({ref.observed_at[:10]}) → {latest.value:g} kg ({latest.observed_at[:10]})"


def derive_nutrition_status(s: Snapshot) -> Optional[Derived]:
    """체중 이력·BMI 만으로 제안. 섭취량·전신상태는 모르므로 '제안' 임을 출처에 명시."""
    w, h = s.value("weight_kg"), s.value("height_cm")
    bmi = w.value / (h.value / 100) ** 2 if w and h and h.value > 0 else None
    losses = {m: weight_loss_pct(s.weight_history, m) for m in (1, 2, 3)}
    reasons = []
    level = "absent"
    if losses[1] and losses[1][0] > 5:
        level, reasons = "severe", [f"1개월 체중감소 {losses[1][0]}%"]
    elif losses[3] and losses[3][0] > 15:
        level, reasons = "severe", [f"3개월 체중감소 {losses[3][0]}%"]
    elif losses[2] and losses[2][0] > 5:
        level, reasons = "moderate", [f"2개월 체중감소 {losses[2][0]}%"]
    elif losses[3] and losses[3][0] > 5:
        level, reasons = "mild", [f"3개월 체중감소 {losses[3][0]}%"]
    if bmi is not None:
        if bmi < 18.5 and level != "severe":
            level, reasons = "severe", reasons + [f"BMI {bmi:.1f} <18.5 (전신상태 저하 동반 시)"]
        elif bmi < 20.5 and level in ("absent", "mild"):
            level, reasons = "moderate", reasons + [f"BMI {bmi:.1f} 18.5-20.5 (전신상태 저하 동반 시)"]
    if not reasons and bmi is None and not any(losses.values()):
        return None
    src = "제안: " + (", ".join(reasons) if reasons else "체중 변화·BMI 이상 없음") + " - 섭취량 감소는 반영되지 않음"
    return Derived(level, src, w.observed_at if w else None)


def derive_loss_3m(s: Snapshot) -> Optional[Derived]:
    r = weight_loss_pct(s.weight_history, 3)
    return Derived(r[0], r[1], s.weight_history[0].observed_at) if r else None


def compute(i: dict) -> Result:
    n = PTS[i["nutrition_status"]]
    d = PTS[i["disease_severity"]]
    a = 1 if i["age"] >= 70 else 0
    total = n + d + a
    if total >= 3:
        label, sev = "영양 위험 - 영양 치료 계획 수립", "danger"
    else:
        label, sev = "위험 낮음 - 매주 재스크리닝", "ok"
    details = [
        Detail("영양상태 손상", next(o.label for o in NUTRITION if o.value == i["nutrition_status"]), n),
        Detail("질병 중증도", next(o.label for o in SEVERITY if o.value == i["disease_severity"]), d),
        Detail("나이 ≥70", f"{i['age']:g}세", a),
    ]
    notes = ["1차 스크리닝(BMI <20.5 · 3개월 체중감소 · 지난주 섭취 감소 · 중증 질환) 중 하나라도 '예' 면 최종 스크리닝을 합니다.",
             "자동 제안은 체중 이력·BMI 만 반영합니다. 섭취량 감소와 전신상태는 직접 확인해 등급을 조정하세요."]
    if i.get("weight_loss_3m_pct") is not None:
        details.append(Detail("3개월 체중 변화 (참고)", f"{i['weight_loss_3m_pct']:+g}% 감소"))
    return Result(value=total, unit="점", label=label, severity=sev, details=details, notes=notes)


SPEC = register(CalculatorSpec(
    id="nrs2002", name="NRS-2002", group="영양",
    description="영양 위험 스크리닝 (ESPEN)",
    inputs=(
        InputSpec("nutrition_status", "영양상태 손상", "select", options=NUTRITION, derive=derive_nutrition_status,
                  help="체중감소율·BMI·지난주 섭취량으로 판정"),
        InputSpec("disease_severity", "질병 중증도 (대사 스트레스)", "select", options=SEVERITY,
                  help="경도: 고관절 골절·급성 합병증 동반 만성질환 / 중등도: 대복부 수술·뇌졸중·중증 폐렴·혈액암 / 중증: 두부 손상·골수이식·중환자"),
        age_input(),
        InputSpec("weight_loss_3m_pct", "3개월 체중감소율 (참고)", "number", unit="%", minimum=-100, maximum=100,
                  required=False, derive=derive_loss_3m),
    ),
    compute=compute,
    references=("Kondrup J et al. Clin Nutr 2003;22:321-36.",),
    scale=Scale(0, 7, (Band(3, "위험 낮음", "ok"), Band(None, "영양 위험", "danger"))),
    guide="입원 환자 영양 위험 선별(ESPEN). 영양상태 손상과 질병 중증도를 각 0~3점으로 더하고 70세 이상이면 1점을 더해 3점 이상이면 영양 치료 계획을 세웁니다.",
))
