"""여러 계산기가 공유하는 입력 정의와 derive 훅."""

from __future__ import annotations

from typing import Optional

from src.calculators.base import Derived, InputSpec, Option
from src.snapshot.model import Snapshot

SEX_OPTIONS = (Option("M", "남"), Option("F", "여"))


def derive_age(s: Snapshot) -> Optional[Derived]:
    if s.patient.age is None:
        return None
    return Derived(s.patient.age, f"Patient 생년월일 {s.patient.birth_date}", category="patient")


def derive_sex(s: Snapshot) -> Optional[Derived]:
    if s.patient.sex is None:
        return None
    return Derived(s.patient.sex, "Patient 성별", category="patient")


def derive_map(s: Snapshot) -> Optional[Derived]:
    """MAP: 기록값이 있으면 그것, 없으면 (SBP + 2·DBP)/3."""
    m = s.value("map")
    if m:
        return Derived(round(m.value, 1), m.source.display, m.observed_at)
    sbp, dbp = s.value("sbp"), s.value("dbp")
    if sbp and dbp:
        return Derived(round((sbp.value + 2 * dbp.value) / 3, 1), "SBP·DBP 에서 계산", sbp.observed_at)
    return None


def derive_ecg_or_vital_hr(s: Snapshot) -> Optional[Derived]:
    """QTc 용 심박수 - 심전도 기록 심박수 우선, 없으면 활력징후 HR."""
    for var in ("ecg_hr", "hr"):
        v = s.value(var)
        if v:
            return Derived(v.value, v.source.display, v.observed_at)
    return None


def age_input(**kw) -> InputSpec:
    return InputSpec("age", "나이", "number", unit="세", minimum=0, maximum=130, derive=derive_age, **kw)


def sex_input(**kw) -> InputSpec:
    return InputSpec("sex", "성별", "select", options=SEX_OPTIONS, derive=derive_sex, **kw)


def flag_input(key: str, label: str, flag: str, help: Optional[str] = None) -> InputSpec:
    return InputSpec(key, label, "boolean", required=True, default=False, flag=flag, help=help)
