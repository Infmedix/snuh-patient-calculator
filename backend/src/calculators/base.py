"""계산기 공통 타입 — 입력 스펙·결과·검증·레지스트리.

프런트 폼은 `CalculatorSpec.inputs` 를 그대로 렌더링하고, 자동 채움(prefill)은
`InputSpec.variable`(스냅샷 정규 변수) / `InputSpec.flag`(진단 플래그) / `InputSpec.derive`
(스냅샷 → 값, 복합 규칙)로 이뤄진다. 계산 자체는 `compute(clean_inputs)` 순수 함수.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from src.snapshot.model import Snapshot

InputType = Literal["number", "boolean", "select"]
Severity = Literal["ok", "info", "warn", "danger"]


@dataclass(frozen=True)
class Option:
    value: str
    label: str


@dataclass(frozen=True)
class Derived:
    """derive 훅의 반환 — 값 + 출처 설명 + (있으면) 기록 시각."""

    value: Any
    source: str
    observed_at: Optional[str] = None
    category: str = "derived"       # prefill 출처 분류 (derived | patient)


@dataclass(frozen=True)
class InputSpec:
    key: str
    label: str
    type: InputType
    unit: Optional[str] = None
    options: tuple[Option, ...] = ()
    required: bool = True
    default: Any = None
    variable: Optional[str] = None            # 스냅샷 정규 변수 이름 (number 자동 채움)
    flag: Optional[str] = None                # 진단 플래그 이름 (boolean 자동 채움)
    derive: Optional[Callable[["Snapshot"], Optional[Derived]]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    help: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "unit": self.unit,
            "required": self.required,
            "default": self.default,
            "variable": self.variable,
            "flag": self.flag,
            "auto": bool(self.variable or self.flag or self.derive),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "help": self.help,
        }
        if self.type == "select":
            d["options"] = [{"value": o.value, "label": o.label} for o in self.options]
        return d


@dataclass(frozen=True)
class Band:
    """구간 막대의 한 칸 — `upto` 미만까지 이 구간 (None = 끝까지)."""

    upto: Optional[float]
    label: str
    severity: Severity


@dataclass(frozen=True)
class Scale:
    """결과 해석용 구간 막대. 프런트가 min~max 사이에 bands 를 그리고 현재 값을 표시한다."""

    min: float
    max: float
    bands: tuple[Band, ...]
    note: Optional[str] = None     # 막대 아래 한 줄 (예: "여성은 >460 ms")

    def to_dict(self) -> dict:
        return {"min": self.min, "max": self.max, "note": self.note,
                "bands": [{"upto": b.upto, "label": b.label, "severity": b.severity} for b in self.bands]}


@dataclass
class Detail:
    label: str
    text: str
    points: Optional[float] = None

    def to_dict(self) -> dict:
        return {"label": self.label, "text": self.text, "points": self.points}


@dataclass
class Result:
    value: Optional[float]           # 대표 수치 (점수 또는 계산값)
    label: str                        # 해석 한 줄 (예: "비만 1단계", "Class B")
    severity: Severity = "info"
    unit: Optional[str] = None
    details: list[Detail] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "unit": self.unit,
            "label": self.label,
            "severity": self.severity,
            "details": [d.to_dict() for d in self.details],
            "notes": self.notes,
            "extra": self.extra,
        }


class InputError(ValueError):
    """입력 검증 실패 — 라우터가 400 으로 변환. `missing` 은 비어 있는 필수 키."""

    def __init__(self, message: str, missing: Optional[list[str]] = None, invalid: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.missing = missing or []
        self.invalid = invalid or {}


@dataclass(frozen=True)
class CalculatorSpec:
    id: str
    name: str
    group: str
    description: str
    inputs: tuple[InputSpec, ...]
    compute: Callable[[dict], Result]
    references: tuple[str, ...] = ()
    scale: Optional[Scale] = None
    guide: Optional[str] = None          # 카드 상단 한두 문장 — 언제 쓰고 어떻게 읽는지

    def input(self, key: str) -> InputSpec:
        for i in self.inputs:
            if i.key == key:
                return i
        raise KeyError(key)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "description": self.description,
            "inputs": [i.to_dict() for i in self.inputs],
            "references": list(self.references),
            "scale": self.scale.to_dict() if self.scale else None,
            "guide": self.guide,
        }

    # ----- 검증 + 실행 -----

    def clean(self, raw: dict) -> dict:
        """원시 입력(JSON) → 타입이 맞는 dict. 필수 누락·형식 오류는 InputError."""
        clean: dict = {}
        missing: list[str] = []
        invalid: dict = {}
        for spec in self.inputs:
            v = raw.get(spec.key, None)
            if v is None or v == "":
                if spec.default is not None:
                    clean[spec.key] = spec.default
                elif spec.required:
                    missing.append(spec.key)
                else:
                    clean[spec.key] = None
                continue
            try:
                clean[spec.key] = _coerce(spec, v)
            except ValueError as e:
                invalid[spec.key] = str(e)
        if missing or invalid:
            parts = []
            if missing:
                parts.append("필수 입력 누락: " + ", ".join(self.input(k).label for k in missing))
            if invalid:
                parts.append("; ".join(f"{self.input(k).label}: {m}" for k, m in invalid.items()))
            raise InputError(" / ".join(parts), missing=missing, invalid=invalid)
        return clean

    def run(self, raw: dict) -> Result:
        return self.compute(self.clean(raw))


def _coerce(spec: InputSpec, v: Any) -> Any:
    if spec.type == "number":
        if isinstance(v, bool):
            raise ValueError("숫자가 필요합니다")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"숫자가 아닙니다: {v!r}")
        if not math.isfinite(f):
            raise ValueError("유한한 숫자가 필요합니다")
        if spec.minimum is not None and f < spec.minimum:
            raise ValueError(f"{spec.minimum} 이상이어야 합니다")
        if spec.maximum is not None and f > spec.maximum:
            raise ValueError(f"{spec.maximum} 이하여야 합니다")
        return f
    if spec.type == "boolean":
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str) and v.lower() in ("true", "false", "1", "0", "yes", "no", "y", "n"):
            return v.lower() in ("true", "1", "yes", "y")
        raise ValueError(f"참/거짓이 아닙니다: {v!r}")
    if spec.type == "select":
        s = str(v)
        if s not in {o.value for o in spec.options}:
            raise ValueError(f"허용되지 않는 값: {s!r}")
        return s
    raise ValueError(f"unknown input type {spec.type}")  # pragma: no cover


# ----- 점수표 도우미 -----

def band(value: float, bands: list[tuple[float, float, float]]) -> float:
    """[lower, upper) 구간표에서 점수를 고른다. 마지막 구간은 상한 포함(inf)."""
    for lo, hi, pts in bands:
        if lo <= value < hi:
            return pts
    raise ValueError(f"구간표에 없는 값: {value}")


INF = float("inf")


# ----- 레지스트리 -----

_REGISTRY: dict[str, CalculatorSpec] = {}
_ORDER: list[str] = []


def register(spec: CalculatorSpec) -> CalculatorSpec:
    if spec.id in _REGISTRY:
        raise RuntimeError(f"duplicate calculator id: {spec.id}")
    _REGISTRY[spec.id] = spec
    _ORDER.append(spec.id)
    return spec


def get(calc_id: str) -> Optional[CalculatorSpec]:
    return _REGISTRY.get(calc_id)


def all_specs() -> list[CalculatorSpec]:
    return [_REGISTRY[i] for i in _ORDER]
