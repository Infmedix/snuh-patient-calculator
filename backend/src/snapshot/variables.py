"""정규 변수 사전 - 원내 항목명(검사항목명·간호어휘명·심전도 구성요소명) → 계산기 변수.

실제 ODS 항목명은 확정되지 않았다 (설계 가정 C). 그래서
  1) 내장 별칭은 영문·한글 관용 표기를 넉넉히 담고,
  2) `APP_VARIABLE_MAP_PATH` YAML 로 변수별 `aliases` / `exclude` 를 **코드 수정 없이** 덮어쓸 수 있다.

매칭 규칙 (`match_variable`):
  - 항목명을 소문자화하고 괄호·구두점을 공백으로 바꿔 토큰화한다.
  - ASCII 4자 이하 별칭은 **토큰 정확 일치** ("ast" 가 "fasting" 에 걸리지 않게), 그 외는 부분 문자열.
  - `exclude` 토큰이 하나라도 들어 있으면 그 변수에는 매칭하지 않는다 (urine creatinine 등).
  - 사전 순서대로 첫 매칭 변수를 쓴다 - 더 구체적인 변수를 먼저 둔다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LAB, VITAL, ECG = "laboratory", "clinical", "exam"


@dataclass(frozen=True)
class VariableDef:
    name: str
    label: str
    unit: Optional[str]
    categories: tuple[str, ...]
    aliases: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    history: bool = False       # 이력 보존 (체중)


_URINE = ("urine", "소변", "요 ", "u-", "u.", "24h", "24hr", "clearance", "ratio", "/cr", "spot")

BUILTIN: tuple[VariableDef, ...] = (
    # ----- 검사실 -----
    VariableDef("creatinine", "크레아티닌", "mg/dL", (LAB,),
                ("creatinine", "크레아티닌", "cr", "crea", "s-cr"), _URINE + ("egfr", "gfr", "cystatin")),
    VariableDef("bun", "BUN", "mg/dL", (LAB,), ("bun", "blood urea nitrogen", "urea nitrogen", "요소질소", "urea"), _URINE),
    VariableDef("sodium", "나트륨", "mmol/L", (LAB,), ("sodium", "나트륨", "na", "na+"), _URINE),
    VariableDef("potassium", "칼륨", "mmol/L", (LAB,), ("potassium", "칼륨", "k", "k+"), _URINE),
    VariableDef("bilirubin_total", "총 빌리루빈", "mg/dL", (LAB,),
                ("total bilirubin", "bilirubin, total", "bilirubin total", "bilirubin(total)", "t.bilirubin", "t-bilirubin",
                 "t.bil", "t-bil", "tbil", "총빌리루빈", "총 빌리루빈", "bilirubin"),
                ("direct", "indirect", "d.bil", "d-bil", "dbil", "직접", "간접", "neonat", "신생아") + _URINE),
    VariableDef("albumin", "알부민", "g/dL", (LAB,), ("albumin", "알부민", "alb"),
                ("micro", "prealbumin", "pre-albumin", "ascit", "복수", "csf", "뇨", "/creat") + _URINE),
    VariableDef("inr", "INR", None, (LAB,), ("inr", "pt(inr)", "pt (inr)", "pt-inr", "pt inr", "prothrombin time inr")),
    VariableDef("platelets", "혈소판", "×10³/µL", (LAB,), ("platelet", "platelets", "plt", "혈소판", "혈소판수"),
                ("mpv", "pdw", "pct", "antibody", "aggreg", "function", "ipf")),
    VariableDef("wbc", "백혈구", "×10³/µL", (LAB,), ("wbc", "white blood cell", "leukocyte", "백혈구", "백혈구수"),
                ("csf", "urine", "소변", "differential", "fluid", "체액")),
    VariableDef("hematocrit", "헤마토크릿", "%", (LAB,), ("hematocrit", "hct", "헤마토크릿", "적혈구용적률")),
    VariableDef("ast", "AST", "U/L", (LAB,), ("ast", "sgot", "got", "aspartate aminotransferase")),
    VariableDef("alt", "ALT", "U/L", (LAB,), ("alt", "sgpt", "gpt", "alanine aminotransferase")),
    VariableDef("alp", "ALP", "U/L", (LAB,), ("alp", "alkaline phosphatase", "알칼리인산분해효소"), ("bone", "isoenzyme")),
    VariableDef("ph", "동맥혈 pH", None, (LAB,), ("ph", "ph(a)", "ph (a)", "arterial ph", "ph arterial", "ph, arterial"),
                ("urine", "소변", "venous", "정맥", "(v)", "ph(v)", "capillary", "pleural", "흉수", "ascit")),
    VariableDef("pao2", "PaO₂", "mmHg", (LAB,), ("pao2", "po2", "po2(a)", "o2 pressure", "partial pressure of oxygen", "산소분압"),
                ("venous", "정맥", "(v)", "pvo2", "fio2")),
    VariableDef("paco2", "PaCO₂", "mmHg", (LAB,), ("paco2", "pco2", "pco2(a)", "co2 pressure", "이산화탄소분압"),
                ("venous", "정맥", "(v)", "pvco2", "etco2")),
    VariableDef("hco3", "HCO₃⁻", "mmol/L", (LAB,), ("hco3", "hco3-", "bicarbonate", "bicarb", "중탄산"), ("venous", "정맥", "(v)", "std")),
    # ----- 간호기록 (활력징후·신체계측) -----
    VariableDef("sbp", "수축기 혈압", "mmHg", (VITAL,), ("수축기", "sbp", "systolic", "수축기혈압", "수축기 혈압")),
    VariableDef("dbp", "이완기 혈압", "mmHg", (VITAL,), ("이완기", "dbp", "diastolic", "이완기혈압", "이완기 혈압")),
    VariableDef("map", "평균동맥압", "mmHg", (VITAL,), ("map", "mean arterial", "평균동맥압", "평균 동맥압")),
    VariableDef("hr", "심박수", "/분", (VITAL,), ("맥박", "pulse", "hr", "heart rate", "심박수", "pulse rate", "pr"), ("ecg",)),
    VariableDef("rr", "호흡수", "/분", (VITAL,), ("호흡", "rr", "respiration", "respiratory rate", "호흡수", "resp")),
    VariableDef("temp_c", "체온", "℃", (VITAL,), ("체온", "bt", "temp", "temperature", "body temperature")),
    VariableDef("spo2", "SpO₂", "%", (VITAL,), ("spo2", "산소포화도", "o2 sat", "oxygen saturation", "sat")),
    VariableDef("gcs", "GCS", None, (VITAL,), ("gcs", "glasgow", "glasgow coma", "gcs total", "gcs 합계"), ("eye", "verbal", "motor", "e)", "v)", "m)")),
    VariableDef("urine_output_24h", "24시간 소변량", "mL/일", (VITAL,),
                ("24시간 소변량", "24h urine", "24hr urine", "urine output 24", "일일 소변량", "소변량(24", "total urine output", "소변 총량", "소변량")),
    VariableDef("fio2", "FiO₂", "분율", (VITAL, LAB), ("fio2", "흡입산소농도", "산소농도")),
    VariableDef("weight_kg", "체중", "kg", (VITAL,), ("체중", "weight", "wt", "bw", "body weight"), ("출생", "birth", "ideal", "표준"), history=True),
    VariableDef("height_cm", "신장", "cm", (VITAL,), ("신장", "키", "height", "ht", "body height")),
    # ----- 심전도 (exam) -----
    VariableDef("qtc_ms", "QTc", "ms", (ECG,), ("qtc", "qtcb", "qtcf", "qt corrected", "corrected qt", "보정 qt", "교정 qt")),
    VariableDef("qt_ms", "QT", "ms", (ECG,), ("qt", "qt interval", "qt 간격", "qt간격"), ("qtc", "dispersion", "corrected")),
    VariableDef("ecg_hr", "심전도 심박수", "/분", (ECG,),
                ("심박수", "heart rate", "hr", "ventricular rate", "vent. rate", "vent rate", "심실박동수", "rate")),
)


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^0-9a-z가-힣+\-.]+", name) if t]


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _alias_hits(alias: str, norm: str, tokens: list[str]) -> bool:
    a = alias.lower().strip()
    if not a:
        return False
    if " " not in a and len(a) <= 4 and a.isascii():
        return a in tokens
    return a in norm


class VariableMap:
    def __init__(self, defs: tuple[VariableDef, ...]):
        self.defs = defs
        self.by_name = {d.name: d for d in defs}

    def match(self, display: str, category: str) -> Optional[VariableDef]:
        if not display:
            return None
        norm = normalize(display)
        tokens = _tokens(norm)
        for d in self.defs:
            if category not in d.categories:
                continue
            if any(ex in norm for ex in d.exclude):
                continue
            if any(_alias_hits(a, norm, tokens) for a in d.aliases):
                return d
        return None

    def get(self, name: str) -> Optional[VariableDef]:
        return self.by_name.get(name)

    def with_overrides(self, overrides: dict) -> "VariableMap":
        """YAML 덮어쓰기: {변수명: {aliases: [...], exclude: [...], add_aliases: [...]}}."""
        defs = []
        for d in self.defs:
            o = overrides.get(d.name)
            if not o:
                defs.append(d)
                continue
            aliases = tuple(o["aliases"]) if "aliases" in o else d.aliases
            if "add_aliases" in o:
                aliases = aliases + tuple(o["add_aliases"])
            exclude = tuple(o["exclude"]) if "exclude" in o else d.exclude
            if "add_exclude" in o:
                exclude = exclude + tuple(o["add_exclude"])
            defs.append(replace(d, aliases=aliases, exclude=exclude))
        unknown = set(overrides) - {d.name for d in self.defs}
        if unknown:
            logger.warning("변수 매핑 덮어쓰기에 알 수 없는 변수: %s", ", ".join(sorted(unknown)))
        return VariableMap(tuple(defs))

    def to_dict(self) -> list[dict]:
        return [{"name": d.name, "label": d.label, "unit": d.unit, "categories": list(d.categories),
                 "aliases": list(d.aliases), "exclude": list(d.exclude)} for d in self.defs]


_DEFAULT = VariableMap(BUILTIN)
_loaded: dict = {"path": None, "map": _DEFAULT}


def load_variable_map(path: Optional[str]) -> VariableMap:
    """env 경로의 YAML 을 읽어 덮어쓴 사전. 파일 문제는 경고 후 내장 사전으로 강등 (부팅을 막지 않는다)."""
    if not path:
        return _DEFAULT
    try:
        import yaml
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("최상위는 {변수명: {...}} 매핑이어야 합니다")
        vm = _DEFAULT.with_overrides(data)
        logger.info("변수 매핑 덮어쓰기 적용: %s (%d개 변수)", path, len(data))
        return vm
    except Exception:
        logger.error("변수 매핑 파일을 읽지 못했습니다 (%s) - 내장 별칭만 사용", path, exc_info=True)
        return _DEFAULT


def current() -> VariableMap:
    from src import settings
    if _loaded["path"] != settings.VARIABLE_MAP_PATH:
        _loaded["map"] = load_variable_map(settings.VARIABLE_MAP_PATH)
        _loaded["path"] = settings.VARIABLE_MAP_PATH
    return _loaded["map"]
