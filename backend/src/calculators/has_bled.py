"""HAS-BLED — 항응고 치료 중 주요 출혈 위험.

H 조절되지 않는 고혈압(SBP >160) 1 / A 신장이상(투석·이식·Cr >2.26 mg/dL) 1 + 간이상(간경변 또는
빌리루빈 >2×ULN 과 AST/ALT/ALP >3×ULN) 1 / S 뇌졸중 병력 1 / B 출혈 병력·소인 1 / L 불안정 INR 1 /
E 65세 초과 1 / D 항혈소판·NSAID 1 + 음주 1.  Pisters R et al. Chest 2010;138:1093-100.
≥3 고위험 — 항응고를 피하라는 뜻이 아니라 교정 가능한 인자를 다루고 더 자주 추적하라는 뜻.
"""

from __future__ import annotations

from typing import Optional

from src.calculators.base import CalculatorSpec, Derived, Detail, InputSpec, Result, register
from src.snapshot.model import Snapshot

BILI_ULN = 1.2    # mg/dL
AST_ULN = 40
ALT_ULN = 40
ALP_ULN = 120


def derive_uncontrolled_htn(s: Snapshot) -> Optional[Derived]:
    v = s.value("sbp")
    if not v:
        return None
    return Derived(v.value > 160, f"SBP {v.value:g} mmHg ({v.source.display})", v.observed_at)


def derive_renal(s: Snapshot) -> Optional[Derived]:
    cr = s.value("creatinine")
    flag = s.flag("renal_disease")
    if cr and cr.value > 2.26:
        return Derived(True, f"Cr {cr.value:g} mg/dL > 2.26", cr.observed_at)
    if flag:
        return Derived(True, "진단: 만성신질환/투석/이식 (" + ", ".join(s.flags["renal_disease"].codes[:3]) + ")")
    if cr or flag is not None:
        return Derived(False, "Cr ≤2.26 이고 해당 진단 없음", cr.observed_at if cr else None)
    return None


def derive_liver(s: Snapshot) -> Optional[Derived]:
    flag = s.flag("liver_disease")
    if flag:
        return Derived(True, "진단: 만성 간질환 (" + ", ".join(s.flags["liver_disease"].codes[:3]) + ")")
    bili = s.value("bilirubin_total")
    if bili and bili.value > 2 * BILI_ULN:
        enz = [(s.value("ast"), 3 * AST_ULN), (s.value("alt"), 3 * ALT_ULN), (s.value("alp"), 3 * ALP_ULN)]
        if any(v and v.value > cut for v, cut in enz):
            return Derived(True, f"빌리루빈 {bili.value:g} >2×ULN 및 간효소 >3×ULN", bili.observed_at)
    if flag is not None or bili:
        return Derived(False, "간질환 진단 없음 / 검사 기준 미충족", bili.observed_at if bili else None)
    return None


def derive_stroke(s: Snapshot) -> Optional[Derived]:
    f = s.flag("stroke_tia")
    if f is None:
        return None
    return Derived(f, "진단 코드 기반" if f else "해당 진단 없음")


def derive_bleeding(s: Snapshot) -> Optional[Derived]:
    f = s.flag("bleeding_history")
    if f is None:
        return None
    return Derived(f, "진단 코드 기반" if f else "해당 진단 없음")


def derive_elderly(s: Snapshot) -> Optional[Derived]:
    if s.patient.age is None:
        return None
    return Derived(s.patient.age > 65, f"나이 {s.patient.age}세")


ITEMS = (
    ("hypertension", "조절되지 않는 고혈압 (SBP >160) (H)"),
    ("renal_abnormal", "신장 기능 이상 (투석·이식·Cr >2.26) (A)"),
    ("liver_abnormal", "간 기능 이상 (간경변·빌리루빈 >2×ULN + 효소 >3×ULN) (A)"),
    ("stroke", "뇌졸중 병력 (S)"),
    ("bleeding", "출혈 병력 또는 소인 (B)"),
    ("labile_inr", "불안정한 INR (TTR <60%) (L)"),
    ("elderly", "65세 초과 (E)"),
    ("drugs", "항혈소판제·NSAID 병용 (D)"),
    ("alcohol", "음주 (≥8잔/주) (D)"),
)


def compute(i: dict) -> Result:
    details = [Detail(label, "예" if i[k] else "아니오", 1 if i[k] else 0) for k, label in ITEMS]
    score = sum(1 for k, _ in ITEMS if i[k])
    if score >= 3:
        label, sev = "고위험 — 교정 가능한 출혈 인자 관리·잦은 추적", "danger"
    elif score == 2:
        label, sev = "중간 위험", "warn"
    else:
        label, sev = "저위험", "ok"
    return Result(value=score, unit="점", label=label, severity=sev, details=details,
                  notes=["높은 점수는 항응고 금기가 아니라 출혈 인자 교정과 추적 강화의 근거입니다 (ESC 2020).",
                         "불안정 INR·약물·음주는 자동으로 알 수 없어 직접 입력합니다."])


def _b(key, label, derive=None, flag=None, help=None):
    return InputSpec(key, label, "boolean", default=False, derive=derive, flag=flag, help=help)


SPEC = register(CalculatorSpec(
    id="has_bled", name="HAS-BLED", group="심혈관",
    description="항응고 치료 중 출혈 위험 평가",
    inputs=(
        _b("hypertension", "조절되지 않는 고혈압 (SBP >160)", derive=derive_uncontrolled_htn),
        _b("renal_abnormal", "신장 기능 이상", derive=derive_renal, help="투석·신장이식·Cr >2.26 mg/dL"),
        _b("liver_abnormal", "간 기능 이상", derive=derive_liver, help="간경변 또는 빌리루빈 >2×ULN + AST/ALT/ALP >3×ULN"),
        _b("stroke", "뇌졸중 병력", derive=derive_stroke),
        _b("bleeding", "출혈 병력 / 소인", derive=derive_bleeding, help="주요 출혈 병력, 빈혈, 출혈 경향"),
        _b("labile_inr", "불안정한 INR", help="와파린 사용 시 TTR <60%"),
        _b("elderly", "65세 초과", derive=derive_elderly),
        _b("drugs", "항혈소판제 / NSAID 병용"),
        _b("alcohol", "음주 (≥8잔/주)"),
    ),
    compute=compute,
    references=("Pisters R et al. Chest 2010;138:1093-100.",),
))

