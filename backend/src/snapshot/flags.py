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


# ----- Charlson 동반질환 (Quan H et al. Med Care 2005 ICD-10 알고리즘) - 플래그 이름 "cci_" + 키 -----
CHARLSON: tuple[FlagDef, ...] = (
    FlagDef("cci_mi", "심근경색", ("I21", "I22", "I252")),
    FlagDef("cci_chf", "울혈성 심부전", ("I099", "I110", "I130", "I132", "I255", "I420", "I425", "I426", "I427", "I428", "I429", "I43", "I50", "P290")),
    FlagDef("cci_pvd", "말초혈관질환", ("I70", "I71", "I731", "I738", "I739", "I771", "I790", "I792", "K551", "K558", "K559", "Z958", "Z959")),
    FlagDef("cci_cerebrovascular", "뇌혈관질환", ("G45", "G46", "H340") + _range("I", 60, 69)),
    FlagDef("cci_dementia", "치매", ("F00", "F01", "F02", "F03", "F051", "G30", "G311")),
    FlagDef("cci_copd", "만성 폐질환", ("I278", "I279") + _range("J", 40, 47) + _range("J", 60, 67) + ("J684", "J701", "J703")),
    FlagDef("cci_rheumatic", "결합조직질환", ("M05", "M06", "M315", "M32", "M33", "M34", "M351", "M353", "M360")),
    FlagDef("cci_pud", "소화성 궤양", _range("K", 25, 28)),
    FlagDef("cci_mild_liver", "경증 간질환", ("B18", "K700", "K701", "K702", "K703", "K709", "K713", "K714", "K715", "K717", "K73", "K74",
                                        "K760", "K762", "K763", "K764", "K768", "K769", "Z944")),
    FlagDef("cci_diabetes", "당뇨 (합병증 없음)", tuple(f"E{n}{s}" for n in (10, 11, 12, 13, 14) for s in ("0", "1", "6", "8", "9"))),
    FlagDef("cci_diabetes_complicated", "당뇨 (만성 합병증)", tuple(f"E{n}{s}" for n in (10, 11, 12, 13, 14) for s in ("2", "3", "4", "5", "7"))),
    FlagDef("cci_hemiplegia", "편마비·하반신마비", ("G041", "G114", "G801", "G802", "G81", "G82", "G830", "G831", "G832", "G833", "G834", "G839")),
    FlagDef("cci_renal", "중등도 이상 신질환", ("I120", "I131", "N032", "N033", "N034", "N035", "N036", "N037", "N052", "N053", "N054", "N055",
                                          "N056", "N057", "N18", "N19", "N250", "Z490", "Z491", "Z492", "Z940", "Z992")),
    FlagDef("cci_malignancy", "악성종양", _range("C", 0, 26) + _range("C", 30, 34) + _range("C", 37, 41) + ("C43",) + _range("C", 45, 58)
            + _range("C", 60, 76) + _range("C", 81, 85) + ("C88",) + _range("C", 90, 97)),
    FlagDef("cci_severe_liver", "중등도-중증 간질환", ("I850", "I859", "I864", "I982", "K704", "K711", "K721", "K729", "K765", "K766", "K767")),
    FlagDef("cci_metastatic", "전이성 고형암", _range("C", 77, 80)),
    FlagDef("cci_aids", "AIDS", ("B20", "B21", "B22", "B24")),
)


def normalize_code(code: str) -> str:
    return code.replace(".", "").replace(" ", "").upper()


def derive_flags(conditions: list[ConditionItem]) -> dict[str, FlagEvidence]:
    out: dict[str, FlagEvidence] = {}
    for f in FLAGS + CHARLSON:
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
    return {f.name: f.label for f in FLAGS + CHARLSON}
