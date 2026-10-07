"""FHIR 번들 → Snapshot. snuh-fhir 의 카테고리별 Observation 구조를 그대로 따른다 (Observation_API.md).

- laboratory: `component[].code.coding[0].display` = 검사항목명, `valueQuantity.value` 는 **문자열**.
  component 가 없는 단일 결과는 `code.coding[0].display`(검사분류명) 로는 항목을 알 수 없어 건너뛴다
  (매뉴얼: 단일 결과는 분류명만 노출) - 단, `valueQuantity` 와 함께 component 가 같이 오면 component 를 쓴다.
- clinical: `code.coding[0].display` = 간호항목명, `valueCodeableConcept.coding[0].display` = 간호어휘명,
  `valueCodeableConcept.text` = 기록 내용. 어휘명 → 항목명 순으로 변수를 찾고 값은 text 에서 숫자를 뽑는다.
  "118/72" 형태의 혈압은 SBP·DBP 로 쪼갠다.
- exam: `component[].code.coding[0].display` = 양식구성요소명, `valueString` 에서 숫자를 뽑는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from src.snapshot.flags import derive_flags
from src.snapshot.model import (ConditionItem, ObservedValue, PatientInfo, Snapshot, Source, WeightPoint)
from src.snapshot.variables import ECG, LAB, VITAL, VariableMap

_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
_BP = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")


@dataclass
class Candidate:
    variable: str
    value: float
    unit: Optional[str]
    observed_at: Optional[str]
    display: str
    category: str
    resource_id: Optional[str]


# ----- 값 파싱 -----

def parse_number(text) -> Optional[float]:
    """'1.8', '<0.1', '>500', '1,234', '96회/분', '94 %' → 숫자. 숫자가 없거나 음성/양성 문구면 None."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    s = str(text).replace(",", "").strip()
    m = _NUM.search(s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.replace(tzinfo=None) if d.tzinfo else d
    except ValueError:
        return None


def _newer(a: Optional[str], b: Optional[str]) -> bool:
    """a 가 b 보다 최신인가. 파싱 불가는 가장 오래된 것으로 본다."""
    da, db = parse_dt(a), parse_dt(b)
    if da and db:
        return da > db
    return da is not None and db is None


# ----- 단위 정규화 -----

def normalize_value(variable: str, value: float, unit: Optional[str]) -> tuple[float, Optional[str]]:
    """원 단위가 정규 단위와 다를 때만 환산한다. 모르는 단위는 값·단위를 그대로 둔다."""
    u = (unit or "").lower().replace(" ", "")
    if variable in ("platelets", "wbc"):
        if value >= 10000 and not any(k in u for k in ("10^3", "10³", "k/", "x10", "×10", "10e3", "thou")):
            return round(value / 1000, 1), "×10³/µL"
        return value, "×10³/µL"
    if variable in ("creatinine",) and ("umol" in u or "µmol" in u or "μmol" in u):
        return round(value / 88.4, 2), "mg/dL"
    if variable == "bilirubin_total" and ("umol" in u or "µmol" in u or "μmol" in u):
        return round(value / 17.1, 2), "mg/dL"
    if variable == "albumin" and u == "g/l":
        return round(value / 10, 2), "g/dL"
    if variable == "bun" and "mmol" in u:
        return round(value * 2.8, 1), "mg/dL"
    if variable == "temp_c" and (value > 50 or "f" == u.strip("°")):
        return round((value - 32) * 5 / 9, 1), "℃"
    if variable == "height_cm" and value < 3:
        return round(value * 100, 1), "cm"
    if variable == "fio2" and value > 1:
        return round(value / 100, 2), "분율"
    return value, unit or None


# ----- 번들 순회 -----

def _entries(bundles: Iterable[dict]) -> Iterable[dict]:
    for b in bundles or ():
        for e in b.get("entry") or ():
            r = e.get("resource") if isinstance(e, dict) else None
            if r:
                yield r


def _display(codeable: Optional[dict]) -> str:
    if not codeable:
        return ""
    for c in codeable.get("coding") or ():
        if c.get("display"):
            return c["display"]
    return codeable.get("text") or ""


def _rid(res: dict) -> Optional[str]:
    for i in res.get("identifier") or ():
        if i.get("value"):
            return i["value"]
    return res.get("id")


def lab_candidates(bundles: Iterable[dict], vm: VariableMap) -> list[Candidate]:
    out = []
    for res in _entries(bundles):
        if res.get("resourceType") != "Observation":
            continue
        when = res.get("effectiveDateTime") or res.get("issued")
        rid = _rid(res)
        for comp in res.get("component") or ():
            disp = _display(comp.get("code"))
            d = vm.match(disp, LAB)
            if not d:
                continue
            q = comp.get("valueQuantity") or {}
            v = parse_number(q.get("value"))
            if v is None:
                continue
            v, unit = normalize_value(d.name, v, q.get("unit") or q.get("code"))
            out.append(Candidate(d.name, v, unit, when, disp, LAB, rid))
    return out


def clinical_candidates(bundles: Iterable[dict], vm: VariableMap) -> list[Candidate]:
    out = []
    for res in _entries(bundles):
        if res.get("resourceType") != "Observation":
            continue
        when = res.get("effectiveDateTime")
        rid = _rid(res)
        vcc = res.get("valueCodeableConcept") or {}
        vocab = _display(vcc)
        item = _display(res.get("code"))
        text = vcc.get("text") or ""
        # 혈압 "118/72" - 어휘명이 수축기/이완기로 갈리지 않은 기록
        bp = _BP.search(text)
        label = vocab or item
        if bp and _is_bp_label(label):
            out.append(Candidate("sbp", float(bp.group(1)), "mmHg", when, label, VITAL, rid))
            out.append(Candidate("dbp", float(bp.group(2)), "mmHg", when, label, VITAL, rid))
            continue
        d = vm.match(vocab, VITAL) or vm.match(item, VITAL)
        if not d:
            continue
        v = parse_number(text) if text else parse_number(vocab)
        if v is None:
            continue
        v, unit = normalize_value(d.name, v, d.unit)
        out.append(Candidate(d.name, v, unit, when, vocab or item, VITAL, rid))
    return out


def _is_bp_label(label: str) -> bool:
    n = label.lower()
    return any(k in n for k in ("혈압", "bp", "blood pressure")) and not any(k in n for k in ("수축", "이완", "systolic", "diastolic", "map", "평균"))


def exam_candidates(bundles: Iterable[dict], vm: VariableMap) -> list[Candidate]:
    out = []
    for res in _entries(bundles):
        if res.get("resourceType") != "Observation":
            continue
        when = res.get("effectiveDateTime") or res.get("issued")
        rid = _rid(res)
        for comp in res.get("component") or ():
            disp = _display(comp.get("code"))
            d = vm.match(disp, ECG)
            if not d:
                continue
            v = parse_number(comp.get("valueString") or (comp.get("valueQuantity") or {}).get("value"))
            if v is None:
                continue
            out.append(Candidate(d.name, v, d.unit, when, disp, ECG, rid))
    return out


def condition_items(bundles: Iterable[dict]) -> list[ConditionItem]:
    """코드 중복 제거 (최신 recordedDate 유지), 최신순."""
    best: dict[str, ConditionItem] = {}
    for res in _entries(bundles):
        if res.get("resourceType") != "Condition":
            continue
        code = None
        display = None
        for c in (res.get("code") or {}).get("coding") or ():
            if c.get("code"):
                code, display = c["code"], c.get("display")
                break
        if not code:
            continue
        item = ConditionItem(code=code, display=display or (res.get("code") or {}).get("text"), recorded_date=res.get("recordedDate"))
        cur = best.get(code)
        if cur is None or (item.recorded_date or "") > (cur.recorded_date or ""):
            best[code] = item
    return sorted(best.values(), key=lambda c: c.recorded_date or "", reverse=True)


# ----- 환자 -----

def patient_info(res: Optional[dict], pid: str, today: date) -> PatientInfo:
    if not res:
        return PatientInfo(id=pid)
    name = None
    for n in res.get("name") or ():
        if n.get("text"):
            name = n["text"]
            break
    g = (res.get("gender") or "").strip().upper()
    sex = "M" if g in ("M", "MALE", "남") else "F" if g in ("F", "FEMALE", "여") else None
    bd = res.get("birthDate")
    age = None
    if bd:
        try:
            b = date.fromisoformat(bd[:10])
            age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        except ValueError:
            age = None
    ident = pid
    for i in res.get("identifier") or ():
        if i.get("value"):
            ident = i["value"]
            break
    return PatientInfo(id=ident, name=name, sex=sex, birth_date=bd, age=age)


# ----- 조립 -----

def build_snapshot(
    pid: str,
    patient: Optional[dict],
    lab_bundles: list[dict],
    clinical_bundles: list[dict],
    exam_bundles: list[dict],
    condition_bundles: Optional[list[dict]],
    vm: VariableMap,
    now: datetime,
    warnings: Optional[list[str]] = None,
) -> Snapshot:
    cands = lab_candidates(lab_bundles, vm) + clinical_candidates(clinical_bundles, vm) + exam_candidates(exam_bundles, vm)
    latest: dict[str, Candidate] = {}
    weights: dict[str, WeightPoint] = {}
    for c in cands:
        cur = latest.get(c.variable)
        if cur is None or _newer(c.observed_at, cur.observed_at):
            latest[c.variable] = c
        if c.variable == "weight_kg" and c.observed_at:
            weights[c.observed_at] = WeightPoint(value=c.value, observed_at=c.observed_at)

    values = {
        name: ObservedValue(variable=name, value=c.value, unit=c.unit, observed_at=c.observed_at,
                            source=Source(display=c.display, category=c.category, resource_id=c.resource_id))
        for name, c in latest.items()
    }
    # MAP 파생 - 기록이 없고 SBP·DBP 가 같은 기록이면 계산해 둔다 (SOFA·APACHE II 용)
    if "map" not in values and "sbp" in values and "dbp" in values:
        s, d = values["sbp"], values["dbp"]
        values["map"] = ObservedValue(variable="map", value=round((s.value + 2 * d.value) / 3, 1), unit="mmHg",
                                      observed_at=s.observed_at, derived=True,
                                      source=Source(display="(SBP + 2·DBP)/3", category="derived", resource_id=s.source.resource_id))

    conditions = condition_items(condition_bundles) if condition_bundles is not None else []
    history = sorted(weights.values(), key=lambda w: parse_dt(w.observed_at) or datetime.min, reverse=True)
    return Snapshot(
        patient=patient_info(patient, pid, now.date()),
        fetched_at=now.isoformat(timespec="seconds"),
        values=values,
        weight_history=history,
        conditions=conditions,
        conditions_available=condition_bundles is not None,
        flags=derive_flags(conditions),
        warnings=list(warnings or []),
    )
