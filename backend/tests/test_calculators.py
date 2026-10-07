"""계산기 단위 테스트 — 공개 계산기(MDCalc 등)와 원 논문의 예제값으로 검증한다.

각 계산기는 `src.calculators.all_specs()` 레지스트리를 통해 접근한다 (프런트와 같은 경로).
"""

import math

import pytest

from src import calculators
from src.calculators.base import InputError


def calc(calc_id: str, **inputs):
    spec = calculators.get(calc_id)
    assert spec is not None, calc_id
    return spec.run(inputs)


# ===== 레지스트리 =====

def test_registry_has_all_twelve_calculators_in_display_order():
    ids = [s.id for s in calculators.all_specs()]
    assert ids == [
        "bmi", "egfr", "crcl",
        "cha2ds2_vasc", "has_bled", "qtc",
        "child_pugh", "meld_na",
        "curb65", "sofa", "apache2",
        "nrs2002",
    ]


def test_every_spec_serializes_and_inputs_have_unique_keys():
    for spec in calculators.all_specs():
        d = spec.to_dict()
        keys = [i["key"] for i in d["inputs"]]
        assert len(keys) == len(set(keys)), spec.id
        for i in d["inputs"]:
            if i["type"] == "select":
                assert i["options"], (spec.id, i["key"])


def test_every_spec_has_scale_and_guide_and_bands_are_ascending():
    for spec in calculators.all_specs():
        assert spec.scale is not None and spec.guide, spec.id
        uptos = [b.upto for b in spec.scale.bands]
        assert uptos[-1] is None, spec.id
        finite = [u for u in uptos if u is not None]
        assert finite == sorted(finite) and all(spec.scale.min < u <= spec.scale.max for u in finite), spec.id
        assert spec.to_dict()["scale"]["bands"][0]["label"]


def test_missing_required_input_raises_with_keys():
    with pytest.raises(InputError) as ei:
        calc("bmi", weight_kg=70)
    assert ei.value.missing == ["height_cm"]


def test_invalid_number_is_reported_per_field():
    with pytest.raises(InputError) as ei:
        calc("bmi", weight_kg="abc", height_cm=170)
    assert "weight_kg" in ei.value.invalid


# ===== BMI =====

@pytest.mark.parametrize("w,h,bmi,label", [
    (50, 170, 17.3, "저체중"),
    (60, 170, 20.8, "정상"),
    (68, 170, 23.5, "비만전단계"),
    (75, 170, 26.0, "1단계 비만"),
    (90, 170, 31.1, "2단계 비만"),
    (105, 170, 36.3, "3단계 비만"),
])
def test_bmi_categories_follow_ksso_2022(w, h, bmi, label):
    r = calc("bmi", weight_kg=w, height_cm=h)
    assert r.value == pytest.approx(bmi, abs=0.05)
    assert r.label == label


def test_bmi_rejects_zero_height():
    with pytest.raises(InputError):
        calc("bmi", weight_kg=70, height_cm=0)


# ===== eGFR (CKD-EPI 2021) =====

@pytest.mark.parametrize("cr,age,sex,expected", [
    (1.0, 50, "M", 92),    # MDCalc CKD-EPI 2021
    (1.0, 50, "F", 69),
    (0.6, 30, "F", 124),
    (2.5, 70, "M", 27),
    (6.0, 60, "F", 8),
])
def test_egfr_matches_published_values(cr, age, sex, expected):
    r = calc("egfr", creatinine=cr, age=age, sex=sex)
    assert round(r.value) == expected


def test_egfr_stage_labels():
    assert calc("egfr", creatinine=1.0, age=50, sex="M").label.startswith("G1")
    assert calc("egfr", creatinine=2.5, age=70, sex="M").label.startswith("G4")
    assert calc("egfr", creatinine=6.0, age=60, sex="F").label.startswith("G5")


# ===== CrCl (Cockcroft-Gault) =====

def test_crcl_actual_weight_male():
    r = calc("crcl", age=60, weight_kg=70, creatinine=1.0, sex="M", weight_basis="actual")
    assert r.value == pytest.approx(77.8, abs=0.1)


def test_crcl_female_factor():
    r = calc("crcl", age=60, weight_kg=70, creatinine=1.0, sex="F", weight_basis="actual")
    assert r.value == pytest.approx(77.78 * 0.85, abs=0.1)


def test_crcl_ideal_weight_uses_devine():
    # 남 180cm → IBW = 50 + 0.9*(180-152.4) = 74.84
    r = calc("crcl", age=40, weight_kg=100, creatinine=1.0, sex="M", height_cm=180, weight_basis="ideal")
    assert r.value == pytest.approx(100 * 74.84 / 72, abs=0.1)


def test_crcl_adjusted_weight():
    ibw = 50 + 0.9 * (180 - 152.4)
    adj = ibw + 0.4 * (100 - ibw)
    r = calc("crcl", age=40, weight_kg=100, creatinine=1.0, sex="M", height_cm=180, weight_basis="adjusted")
    assert r.value == pytest.approx(100 * adj / 72, abs=0.1)


def test_crcl_ideal_weight_requires_height():
    with pytest.raises(InputError):
        calc("crcl", age=40, weight_kg=100, creatinine=1.0, sex="M", weight_basis="ideal")


# ===== CHA2DS2-VASc =====

def test_cha2ds2_vasc_max_score_is_nine():
    r = calc("cha2ds2_vasc", age=80, sex="F", heart_failure=True, hypertension=True,
             diabetes=True, stroke_tia=True, vascular_disease=True)
    assert r.value == 9


def test_cha2ds2_vasc_age_bands():
    base = dict(sex="M", heart_failure=False, hypertension=False, diabetes=False,
                stroke_tia=False, vascular_disease=False)
    assert calc("cha2ds2_vasc", age=64, **base).value == 0
    assert calc("cha2ds2_vasc", age=65, **base).value == 1
    assert calc("cha2ds2_vasc", age=75, **base).value == 2


def test_cha2ds2_vasc_female_alone_is_low_risk_label():
    r = calc("cha2ds2_vasc", age=50, sex="F", heart_failure=False, hypertension=False,
             diabetes=False, stroke_tia=False, vascular_disease=False)
    assert r.value == 1
    assert r.severity == "ok"


# ===== HAS-BLED =====

def test_has_bled_scores_each_item_once():
    r = calc("has_bled", hypertension=True, renal_abnormal=True, liver_abnormal=True, stroke=True,
             bleeding=True, labile_inr=True, elderly=True, drugs=True, alcohol=True)
    assert r.value == 9
    assert r.severity == "danger"


def test_has_bled_zero_is_low():
    r = calc("has_bled", hypertension=False, renal_abnormal=False, liver_abnormal=False, stroke=False,
             bleeding=False, labile_inr=False, elderly=False, drugs=False, alcohol=False)
    assert r.value == 0
    assert r.severity == "ok"


# ===== Child-Pugh =====

def test_child_pugh_class_a_minimum():
    r = calc("child_pugh", bilirubin_total=1.0, albumin=4.0, inr=1.2, ascites="none", encephalopathy="none")
    assert r.value == 5
    assert r.label.startswith("Class A")


def test_child_pugh_class_b():
    r = calc("child_pugh", bilirubin_total=2.5, albumin=3.0, inr=2.0, ascites="mild", encephalopathy="none")
    assert r.value == 9
    assert r.label.startswith("Class B")


def test_child_pugh_class_c_maximum():
    r = calc("child_pugh", bilirubin_total=4.0, albumin=2.0, inr=3.0, ascites="moderate_severe",
             encephalopathy="grade_3_4")
    assert r.value == 15
    assert r.label.startswith("Class C")


# ===== MELD-Na =====

def test_meld_na_floor_is_six():
    r = calc("meld_na", creatinine=1.0, bilirubin_total=1.0, inr=1.0, sodium=140, dialysis=False)
    assert r.value == 6


def test_meld_na_sodium_adjustment_applies_above_eleven():
    # MELD(i): 0.957ln2 + 0.378ln3 + 1.12ln1.5 + 0.643 = 2.176 → 2.2 → 22
    # MELD-Na: 22 + 1.32*(137-130) - 0.033*22*7 = 26.16 → 26
    r = calc("meld_na", creatinine=2.0, bilirubin_total=3.0, inr=1.5, sodium=130, dialysis=False)
    assert r.value == 26
    assert r.extra["meld_i"] == 22


def test_meld_na_clamps_creatinine_and_sodium():
    hi = calc("meld_na", creatinine=9.0, bilirubin_total=3.0, inr=1.5, sodium=110, dialysis=False)
    capped = calc("meld_na", creatinine=4.0, bilirubin_total=3.0, inr=1.5, sodium=125, dialysis=False)
    assert hi.value == capped.value


def test_meld_na_dialysis_sets_creatinine_four():
    d = calc("meld_na", creatinine=1.0, bilirubin_total=3.0, inr=1.5, sodium=137, dialysis=True)
    four = calc("meld_na", creatinine=4.0, bilirubin_total=3.0, inr=1.5, sodium=137, dialysis=False)
    assert d.value == four.value


def test_meld_na_ceiling_is_forty():
    r = calc("meld_na", creatinine=4.0, bilirubin_total=30.0, inr=6.0, sodium=125, dialysis=False)
    assert r.value == 40


# ===== CURB-65 =====

def test_curb65_all_criteria():
    r = calc("curb65", confusion=True, bun=25, rr=32, sbp=85, dbp=55, age=70)
    assert r.value == 5
    assert r.severity == "danger"


def test_curb65_boundaries():
    base = dict(confusion=False, age=64)
    assert calc("curb65", bun=19, rr=29, sbp=90, dbp=61, **base).value == 0
    assert calc("curb65", bun=19.1, rr=29, sbp=90, dbp=61, **base).value == 1   # BUN > 19
    assert calc("curb65", bun=19, rr=30, sbp=90, dbp=61, **base).value == 1     # RR ≥ 30
    assert calc("curb65", bun=19, rr=29, sbp=89, dbp=61, **base).value == 1     # SBP < 90
    assert calc("curb65", bun=19, rr=29, sbp=90, dbp=60, **base).value == 1     # DBP ≤ 60
    assert calc("curb65", bun=19, rr=29, sbp=90, dbp=61, confusion=False, age=65).value == 1


# ===== SOFA =====

def _sofa(**over):
    base = dict(pao2=100, fio2=0.21, mechanical_ventilation=False, platelets=200, bilirubin_total=1.0,
                map=80, vasopressor="none", gcs=15, creatinine=1.0, urine_output_24h=None)
    base.update(over)
    return calc("sofa", **base)


def test_sofa_healthy_is_zero():
    assert _sofa().value == 0


def test_sofa_respiration_requires_ventilation_for_three_and_four():
    assert _sofa(pao2=90, fio2=0.5).extra["subscores"]["respiration"] == 2    # PF 180, no vent → 2
    assert _sofa(pao2=90, fio2=0.5, mechanical_ventilation=True).extra["subscores"]["respiration"] == 3
    assert _sofa(pao2=45, fio2=0.5, mechanical_ventilation=True).extra["subscores"]["respiration"] == 4


def test_sofa_accepts_fio2_as_percent():
    assert _sofa(pao2=90, fio2=50).extra["subscores"]["respiration"] == 2


def test_sofa_coagulation_bands():
    assert _sofa(platelets=149).extra["subscores"]["coagulation"] == 1
    assert _sofa(platelets=99).extra["subscores"]["coagulation"] == 2
    assert _sofa(platelets=49).extra["subscores"]["coagulation"] == 3
    assert _sofa(platelets=19).extra["subscores"]["coagulation"] == 4


def test_sofa_liver_bands():
    assert _sofa(bilirubin_total=1.2).extra["subscores"]["liver"] == 1
    assert _sofa(bilirubin_total=2.0).extra["subscores"]["liver"] == 2
    assert _sofa(bilirubin_total=6.0).extra["subscores"]["liver"] == 3
    assert _sofa(bilirubin_total=12.0).extra["subscores"]["liver"] == 4


def test_sofa_cardiovascular_vasopressor_overrides_map():
    assert _sofa(map=65).extra["subscores"]["cardiovascular"] == 1
    assert _sofa(map=65, vasopressor="dopamine_le5_or_dobutamine").extra["subscores"]["cardiovascular"] == 2
    assert _sofa(map=80, vasopressor="dopamine_gt5_or_epi_le0_1").extra["subscores"]["cardiovascular"] == 3
    assert _sofa(map=80, vasopressor="dopamine_gt15_or_epi_gt0_1").extra["subscores"]["cardiovascular"] == 4


def test_sofa_cns_bands():
    assert _sofa(gcs=14).extra["subscores"]["cns"] == 1
    assert _sofa(gcs=12).extra["subscores"]["cns"] == 2
    assert _sofa(gcs=9).extra["subscores"]["cns"] == 3
    assert _sofa(gcs=5).extra["subscores"]["cns"] == 4


def test_sofa_renal_takes_worse_of_creatinine_and_urine_output():
    assert _sofa(creatinine=1.2).extra["subscores"]["renal"] == 1
    assert _sofa(creatinine=1.0, urine_output_24h=450).extra["subscores"]["renal"] == 3
    assert _sofa(creatinine=1.0, urine_output_24h=150).extra["subscores"]["renal"] == 4
    assert _sofa(creatinine=5.0, urine_output_24h=1500).extra["subscores"]["renal"] == 4


def test_sofa_max_is_twenty_four():
    r = _sofa(pao2=40, fio2=1.0, mechanical_ventilation=True, platelets=10, bilirubin_total=15,
              map=40, vasopressor="dopamine_gt15_or_epi_gt0_1", gcs=3, creatinine=6)
    assert r.value == 24


# ===== APACHE II =====

def _apache(**over):
    base = dict(temp_c=37, map=80, hr=80, rr=16, fio2=0.21, pao2=90, paco2=40, ph=7.40, hco3=None,
                sodium=140, potassium=4.0, creatinine=1.0, acute_renal_failure=False, hematocrit=40,
                wbc=8, gcs=15, age=40, chronic_health="none")
    base.update(over)
    return calc("apache2", **base)


def test_apache2_healthy_young_is_zero():
    assert _apache().value == 0


def test_apache2_age_points():
    assert _apache(age=44).extra["age_points"] == 0
    assert _apache(age=45).extra["age_points"] == 2
    assert _apache(age=55).extra["age_points"] == 3
    assert _apache(age=65).extra["age_points"] == 5
    assert _apache(age=75).extra["age_points"] == 6


def test_apache2_chronic_health_points():
    assert _apache(chronic_health="nonoperative_or_emergency_postop").extra["chronic_health_points"] == 5
    assert _apache(chronic_health="elective_postop").extra["chronic_health_points"] == 2


def test_apache2_uses_aado2_when_fio2_at_least_half():
    # FiO2 1.0, PaCO2 40, PaO2 100 → A-aDO2 = 713 - 50 - 100 = 563 → 4점
    r = _apache(fio2=1.0, pao2=100, paco2=40)
    assert r.extra["aps"]["oxygenation"] == 4
    # FiO2 0.21 → PaO2 기준: 60 → 3점
    assert _apache(fio2=0.21, pao2=60).extra["aps"]["oxygenation"] == 3


def test_apache2_requires_paco2_for_high_fio2():
    with pytest.raises(InputError):
        _apache(fio2=0.6, paco2=None)


def test_apache2_falls_back_to_hco3_without_ph():
    assert _apache(ph=None, hco3=16).extra["aps"]["acid_base"] == 3
    with pytest.raises(InputError):
        _apache(ph=None, hco3=None)


def test_apache2_acute_renal_failure_doubles_creatinine_points():
    assert _apache(creatinine=2.0).extra["aps"]["creatinine"] == 3
    assert _apache(creatinine=2.0, acute_renal_failure=True).extra["aps"]["creatinine"] == 6


def test_apache2_gcs_points_are_fifteen_minus_gcs():
    assert _apache(gcs=3).extra["aps"]["gcs"] == 12


def test_apache2_worked_example():
    # 온도 39.5(3) MAP 55(2) HR 130(2) RR 30(1) PaO2 65 FiO2 .3 (1) pH 7.28(2) Na 150(1) K 5.6(1)
    # Cr 1.8(2) Hct 28(2) WBC 18(1) GCS 12(3) 나이 68(5) 만성 없음 → 26
    r = _apache(temp_c=39.5, map=55, hr=130, rr=30, fio2=0.3, pao2=65, ph=7.28, sodium=150,
                potassium=5.6, creatinine=1.8, hematocrit=28, wbc=18, gcs=12, age=68)
    assert r.value == 26


# ===== QTc =====

def test_qtc_formulas_at_sixty_bpm_equal_qt():
    r = calc("qtc", qt_ms=400, hr=60, sex="M")
    for k in ("bazett", "fridericia", "framingham", "hodges"):
        assert r.extra[k] == pytest.approx(400, abs=0.5)


def test_qtc_bazett_at_hundred_bpm():
    r = calc("qtc", qt_ms=360, hr=100, sex="M")
    rr = 0.6
    assert r.extra["bazett"] == pytest.approx(360 / math.sqrt(rr), abs=0.5)
    assert r.extra["fridericia"] == pytest.approx(360 / rr ** (1 / 3), abs=0.5)
    assert r.extra["framingham"] == pytest.approx(360 + 154 * (1 - rr), abs=0.5)
    assert r.extra["hodges"] == pytest.approx(360 + 1.75 * 40, abs=0.5)


def test_qtc_interpretation_by_sex():
    assert calc("qtc", qt_ms=440, hr=60, sex="M").severity == "ok"
    assert calc("qtc", qt_ms=455, hr=60, sex="M").severity == "warn"
    assert calc("qtc", qt_ms=455, hr=60, sex="F").severity == "ok"
    assert calc("qtc", qt_ms=505, hr=60, sex="F").severity == "danger"


# ===== NRS-2002 =====

def test_nrs2002_sums_components_and_age():
    r = calc("nrs2002", nutrition_status="moderate", disease_severity="mild", age=72)
    assert r.value == 4
    assert r.severity == "danger"


def test_nrs2002_below_three_is_not_at_risk():
    r = calc("nrs2002", nutrition_status="mild", disease_severity="mild", age=50)
    assert r.value == 2
    assert r.severity == "ok"
