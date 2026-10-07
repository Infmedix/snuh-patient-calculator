"""번들 → 스냅샷 추출 테스트. fixtures/patients/10000001.json 을 소재로 쓴다."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.snapshot.extract import build_snapshot, normalize_value, parse_number
from src.snapshot.flags import derive_flags, normalize_code
from src.snapshot.model import ConditionItem
from src.snapshot.variables import BUILTIN, VariableMap, load_variable_map

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "patients" / "10000001.json"
NOW = datetime(2026, 10, 7, 9, 0, 0)


def _split(bundle):
    labs, clin, exam, cond, patient = [], [], [], [], None
    for e in bundle["entry"]:
        r = e["resource"]
        if r["resourceType"] == "Patient":
            patient = r
        elif r["resourceType"] == "Condition":
            cond.append(r)
        else:
            cat = r["category"][0]["coding"][0]["code"]
            {"laboratory": labs, "clinical": clin, "exam": exam}[cat].append(r)
    wrap = lambda rs: [{"resourceType": "Bundle", "entry": [{"resource": r} for r in rs]}]
    return patient, wrap(labs), wrap(clin), wrap(exam), wrap(cond)


@pytest.fixture(scope="module")
def snap():
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patient, labs, clin, exam, cond = _split(bundle)
    return build_snapshot("10000001", patient, labs, clin, exam, cond, VariableMap(BUILTIN), NOW)


# ===== 값 파싱 =====

@pytest.mark.parametrize("raw,expected", [
    ("1.8", 1.8), ("<0.1", 0.1), (">500", 500), ("1,234", 1234), ("96회/분", 96), ("94 %", 94),
    ("Negative", None), ("", None), (None, None), (12, 12.0),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_normalize_platelets_per_microliter_to_thousands():
    assert normalize_value("platelets", 95000, "/uL") == (95.0, "×10³/µL")
    assert normalize_value("platelets", 95, "10^3/uL") == (95, "×10³/µL")


def test_normalize_si_units():
    assert normalize_value("creatinine", 88.4, "umol/L") == (1.0, "mg/dL")
    assert normalize_value("albumin", 29, "g/L") == (2.9, "g/dL")
    assert normalize_value("height_cm", 1.7, "m") == (170.0, "cm")
    assert normalize_value("fio2", 40, None) == (0.4, "분율")


# ===== 별칭 매칭 =====

def test_alias_short_ascii_requires_token_match():
    vm = VariableMap(BUILTIN)
    assert vm.match("Glucose (fasting)", "laboratory") is None          # "ast" 가 fasting 에 걸리지 않음
    assert vm.match("AST (SGOT)", "laboratory").name == "ast"
    assert vm.match("K", "laboratory").name == "potassium"


def test_alias_excludes_urine_and_direct_variants():
    vm = VariableMap(BUILTIN)
    assert vm.match("Creatinine (urine)", "laboratory") is None
    assert vm.match("Urine Sodium", "laboratory") is None
    assert vm.match("Direct bilirubin", "laboratory") is None
    assert vm.match("Total bilirubin", "laboratory").name == "bilirubin_total"
    assert vm.match("MPV", "laboratory") is None


def test_alias_respects_category():
    vm = VariableMap(BUILTIN)
    assert vm.match("QT", "exam").name == "qt_ms"
    assert vm.match("QTc", "exam").name == "qtc_ms"
    assert vm.match("심박수", "exam").name == "ecg_hr"
    assert vm.match("맥박", "clinical").name == "hr"
    assert vm.match("QT", "laboratory") is None


def test_variable_map_yaml_override(tmp_path):
    p = tmp_path / "vars.yaml"
    p.write_text("creatinine:\n  aliases: ['크레아티닌(혈청)']\nsodium:\n  add_aliases: ['Na(serum)']\n", encoding="utf-8")
    vm = load_variable_map(str(p))
    assert vm.match("Creatinine", "laboratory") is None
    assert vm.match("크레아티닌(혈청)", "laboratory").name == "creatinine"
    assert vm.match("Na(serum)", "laboratory").name == "sodium"
    assert vm.match("Sodium", "laboratory").name == "sodium"


def test_variable_map_bad_file_falls_back(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("- not a mapping\n", encoding="utf-8")
    vm = load_variable_map(str(p))
    assert vm.match("Creatinine", "laboratory").name == "creatinine"


# ===== 스냅샷 =====

def test_patient_demographics(snap):
    assert snap.patient.id == "10000001"
    assert snap.patient.name == "홍길동"
    assert snap.patient.sex == "M"
    assert snap.patient.age == 68


def test_latest_lab_wins_and_urine_is_ignored(snap):
    cr = snap.values["creatinine"]
    assert cr.value == 1.8
    assert cr.observed_at == "2026-10-05T08:30:00"
    assert cr.source.display == "Creatinine"
    assert cr.source.resource_id == "SPCM20261005001"
    assert snap.values["sodium"].value == 131


def test_lab_values_extracted(snap):
    v = snap.values
    assert v["bun"].value == 32
    assert v["potassium"].value == 4.9
    assert v["bilirubin_total"].value == 2.6
    assert v["albumin"].value == 2.9
    assert v["ast"].value == 85 and v["alt"].value == 60 and v["alp"].value == 180
    assert v["inr"].value == 1.9
    assert v["wbc"].value == 12.5
    assert v["hematocrit"].value == 33.2
    assert v["platelets"].value == 95.0 and v["platelets"].unit == "×10³/µL"
    assert v["ph"].value == 7.31 and v["paco2"].value == 48 and v["pao2"].value == 68 and v["hco3"].value == 22


def test_vitals_including_slash_bp_and_text_units(snap):
    v = snap.values
    assert v["sbp"].value == 118 and v["dbp"].value == 72          # 14:00 "118/72" 가 06:00 개별값보다 최신
    assert v["hr"].value == 96
    assert v["rr"].value == 22
    assert v["temp_c"].value == 38.2
    assert v["spo2"].value == 94
    assert v["gcs"].value == 14
    assert v["urine_output_24h"].value == 900
    assert v["weight_kg"].value == 62.5 and v["height_cm"].value == 170


def test_map_is_derived_from_bp(snap):
    m = snap.values["map"]
    assert m.derived is True
    assert m.value == pytest.approx((118 + 2 * 72) / 3, abs=0.05)


def test_weight_history_is_newest_first(snap):
    assert [w.value for w in snap.weight_history] == [62.5, 66.0]


def test_ecg_components(snap):
    assert snap.values["qt_ms"].value == 398
    assert snap.values["qtc_ms"].value == 503
    assert snap.values["ecg_hr"].value == 96
    assert snap.values["qt_ms"].source.category == "exam"


def test_conditions_deduplicated_newest_first(snap):
    codes = [c.code for c in snap.conditions]
    assert codes.count("I109") == 1
    assert codes[0] == "I480"
    assert snap.conditions[1].code == "I109" and snap.conditions[1].recorded_date == "2026-09-20"


def test_flags_from_kcd_prefixes(snap):
    f = snap.flags
    assert f["hypertension"].present and "I109" in f["hypertension"].codes
    assert f["diabetes"].present
    assert f["atrial_fibrillation"].present
    assert f["liver_disease"].present
    assert f["renal_disease"].present
    assert f["stroke_tia"].present
    assert not f["heart_failure"].present
    assert not f["malignancy"].present
    assert snap.flag("heart_failure") is False


def test_flag_unknown_when_conditions_unavailable():
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patient, labs, clin, exam, _ = _split(bundle)
    s = build_snapshot("10000001", patient, labs, clin, exam, None, VariableMap(BUILTIN), NOW, warnings=["Condition 실패"])
    assert s.conditions_available is False
    assert s.flag("hypertension") is None
    assert s.warnings == ["Condition 실패"]


def test_flag_prefix_handles_dots_and_ranges():
    flags = derive_flags([ConditionItem(code="I11.0"), ConditionItem(code="K92.2"), ConditionItem(code="C34.1")])
    assert flags["heart_failure"].present
    assert flags["hypertension"].present
    assert flags["bleeding_history"].present
    assert flags["malignancy"].present
    assert normalize_code("i 11.0") == "I110"


def test_charlson_flags_from_fixture(snap):
    f = snap.flags
    assert f["cci_mild_liver"].present          # K746
    assert f["cci_renal"].present               # N189
    assert f["cci_cerebrovascular"].present     # I639
    assert f["cci_diabetes"].present and not f["cci_diabetes_complicated"].present   # E119
    assert not f["cci_chf"].present


def test_charlson_quan_prefixes():
    flags = derive_flags([ConditionItem(code="E11.5"), ConditionItem(code="C78.0"), ConditionItem(code="I25.2"), ConditionItem(code="J44.9")])
    assert flags["cci_diabetes_complicated"].present and not flags["cci_diabetes"].present
    assert flags["cci_metastatic"].present and not flags["cci_malignancy"].present
    assert flags["cci_mi"].present and flags["cci_copd"].present
