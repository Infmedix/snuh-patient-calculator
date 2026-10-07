"""진단 플래그 - Condition 의 KCD(ICD-10 계열) 코드 접두 매칭.

Condition 은 「내원 진단」이라 같은 코드가 여러 건 나온다 (snuh-fhir 매뉴얼). 코드를 중복 제거한 뒤
접두로 판정한다. 코드의 점(`I11.0`)은 제거해 비교한다. 결과는 **제안값**이며 화면에서 뒤집을 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.snapshot.model import ConditionItem, FlagEvidence


@dataclass(frozen=True)
class FlagDef:
    name: str
    label: str
    prefixes: tuple[str, ...]


def _range(letter: str, lo: int, hi: int) -> tuple[str, ...]:
    return tuple(f"{letter}{n:02d}" for n in range(lo, hi + 1))


FLAGS: tuple[FlagDef, ...] = (
    FlagDef("hypertension", "고혈압", _range("I", 10, 15)),
    FlagDef("diabetes", "당뇨", _range("E", 10, 14)),
    FlagDef("heart_failure", "심부전", ("I50", "I110", "I130", "I132")),
    FlagDef("stroke_tia", "뇌졸중/TIA", _range("I", 60, 64) + ("G45", "G46")),
    FlagDef("vascular_disease", "혈관질환", ("I21", "I22", "I25", "I70", "I71", "I739")),
    FlagDef("atrial_fibrillation", "심방세동", ("I48",)),
    FlagDef("bleeding_history", "출혈 병력", ("K920", "K921", "K922", "I60", "I61", "I62", "D68", "D69", "R58")),
    FlagDef("renal_disease", "만성 신질환/투석/이식", ("N18", "N19", "Z992", "Z940")),
    FlagDef("liver_disease", "만성 간질환", _range("K", 70, 77)),
    FlagDef("malignancy", "악성 종양", _range("C", 0, 97)),
)


def normalize_code(code: str) -> str:
    return code.replace(".", "").replace(" ", "").upper()


def derive_flags(conditions: list[ConditionItem]) -> dict[str, FlagEvidence]:
    out: dict[str, FlagEvidence] = {}
    for f in FLAGS:
        codes, displays = [], []
        for c in conditions:
            nc = normalize_code(c.code)
            if any(nc.startswith(p) for p in f.prefixes):
                codes.append(c.code)
                if c.display and c.display not in displays:
                    displays.append(c.display)
        out[f.name] = FlagEvidence(present=bool(codes), codes=codes, displays=displays)
    return out


def flag_labels() -> dict[str, str]:
    return {f.name: f.label for f in FLAGS}
