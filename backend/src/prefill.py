"""스냅샷 → 계산기 입력 자동 채움 + 전체 개요.

우선순위: `derive` 훅 → `variable`(수치) → `flag`(진단). 채운 값마다 출처(`source`)를 붙인다.
플래그가 None(Condition 조회 실패)이면 채우지 않는다 - 「모른다」를 False 로 바꾸지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src import settings
from src.calculators import all_specs
from src.calculators.base import CalculatorSpec, InputError
from src.snapshot.extract import parse_dt
from src.snapshot.model import Snapshot


def _stale(observed_at: Optional[str], now: datetime) -> bool:
    d = parse_dt(observed_at)
    return bool(d and (now - d).days > settings.STALE_AFTER_DAYS)


def _entry(value: Any, text: str, category: str, observed_at: Optional[str], now: datetime, derived: bool = False) -> dict:
    return {
        "value": value,
        "source": {"text": text, "category": category, "observed_at": observed_at,
                   "stale": _stale(observed_at, now), "derived": derived},
    }


def prefill(spec: CalculatorSpec, snap: Snapshot, now: datetime) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in spec.inputs:
        if i.derive is not None:
            d = i.derive(snap)
            if d is not None:
                out[i.key] = _entry(d.value, d.source, d.category, d.observed_at, now, derived=(d.category == "derived"))
                continue
        if i.variable:
            v = snap.value(i.variable)
            if v is not None:
                unit = f" {v.unit}" if v.unit else ""
                out[i.key] = _entry(v.value, f"{v.source.display} {v.value:g}{unit}", v.source.category, v.observed_at, now,
                                    derived=v.derived)
                continue
        if i.flag:
            f = snap.flag(i.flag)
            if f is not None:
                ev = snap.flags.get(i.flag)
                text = ("진단: " + ", ".join(ev.codes[:4])) if (f and ev and ev.codes) else "해당 진단 코드 없음"
                out[i.key] = _entry(f, text, "condition", None, now)
    return out


def overview(snap: Snapshot, now: datetime) -> list[dict]:
    """계산기마다 prefill 과, 필수값이 다 있으면 계산 결과를 함께 돌려준다."""
    items = []
    for spec in all_specs():
        pre = prefill(spec, snap, now)
        raw = {k: v["value"] for k, v in pre.items()}
        result, missing, error = None, [], None
        try:
            result = spec.run(raw).to_dict()
        except InputError as e:
            missing = e.missing
            error = e.message if e.invalid else None
        items.append({"id": spec.id, "prefill": pre, "result": result, "missing": missing, "error": error})
    return items
