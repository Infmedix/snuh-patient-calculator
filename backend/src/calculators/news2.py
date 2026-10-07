"""NEWS2 - National Early Warning Score 2 (Royal College of Physicians 2017).

호흡수 ≤8 3 · 9-11 1 · 12-20 0 · 21-24 2 · ≥25 3
SpO₂ 척도 1: ≤91 3 · 92-93 2 · 94-95 1 · ≥96 0
SpO₂ 척도 2(고탄산혈증 호흡부전, 목표 88-92%): ≤83 3 · 84-85 2 · 86-87 1 · 88-92 0 · 93-94(산소) 1 · 95-96(산소) 2 · ≥97(산소) 3 · ≥93(공기) 0
산소 투여 2 · SBP ≤90 3 · 91-100 2 · 101-110 1 · 111-219 0 · ≥220 3
HR ≤40 3 · 41-50 1 · 51-90 0 · 91-110 1 · 111-130 2 · ≥131 3
의식: Alert 0 · CVPU(새로 생긴 혼돈 포함) 3
체온 ≤35.0 3 · 35.1-36.0 1 · 36.1-38.0 0 · 38.1-39.0 1 · ≥39.1 2
합계 0-20. 0-4 저위험(한 항목 3점이면 저-중) · 5-6 중간(긴급 평가) · ≥7 고위험(응급 대응).
"""

from __future__ import annotations

from typing import Optional

from src.calculators.base import INF, Band, CalculatorSpec, Derived, Detail, InputSpec, Option, Result, Scale, band, register
from src.snapshot.model import Snapshot

RR = [(25, INF, 3), (21, 25, 2), (12, 21, 0), (9, 12, 1), (-INF, 9, 3)]
SBP = [(220, INF, 3), (111, 220, 0), (101, 111, 1), (91, 101, 2), (-INF, 91, 3)]
HR = [(131, INF, 3), (111, 131, 2), (91, 111, 1), (51, 91, 0), (41, 51, 1), (-INF, 41, 3)]
TEMP = [(39.1, INF, 2), (38.1, 39.1, 1), (36.1, 38.1, 0), (35.1, 36.1, 1), (-INF, 35.1, 3)]
SPO2_1 = [(96, INF, 0), (94, 96, 1), (92, 94, 2), (-INF, 92, 3)]


def spo2_points(spo2: float, scale: str, on_oxygen: bool) -> int:
    if scale == "1":
        return int(band(spo2, SPO2_1))
    # 척도 2
    if spo2 <= 83:
        return 3
    if spo2 <= 85:
        return 2
    if spo2 <= 87:
        return 1
    if spo2 <= 92:
        return 0
    if not on_oxygen:
        return 0
    if spo2 <= 94:
        return 1
    if spo2 <= 96:
        return 2
    return 3


def derive_on_oxygen(s: Snapshot) -> Optional[Derived]:
    f = s.value("fio2")
    if not f:
        return None
    return Derived(f.value > 0.21, f"FiO₂ {f.value:g} ({f.source.display})", f.observed_at)


def derive_consciousness(s: Snapshot) -> Optional[Derived]:
    g = s.value("gcs")
    if not g:
        return None
    return Derived("alert" if g.value >= 15 else "cvpu", f"GCS {g.value:g} ({g.source.display})", g.observed_at)


def compute(i: dict) -> Result:
    pts = {
        "rr": int(band(i["rr"], RR)),
        "spo2": spo2_points(i["spo2"], i["spo2_scale"], i["on_oxygen"]),
        "oxygen": 2 if i["on_oxygen"] else 0,
        "sbp": int(band(i["sbp"], SBP)),
        "hr": int(band(i["hr"], HR)),
        "consciousness": 0 if i["consciousness"] == "alert" else 3,
        "temp": int(band(i["temp_c"], TEMP)),
    }
    total = sum(pts.values())
    single3 = any(v == 3 for k, v in pts.items() if k != "oxygen")
    if total >= 7:
        label, sev = "고위험 - 응급 대응 (중환자 평가)", "danger"
    elif total >= 5 or single3:
        label, sev = ("중간 - 긴급 평가" if total >= 5 else "저-중간 - 한 항목 3점, 긴급 평가"), "warn"
    else:
        label, sev = "저위험 - 정기 관찰", "ok"
    details = [
        Detail("호흡수", f"{i['rr']:g}/분", pts["rr"]),
        Detail(f"SpO₂ (척도 {i['spo2_scale']})", f"{i['spo2']:g} %", pts["spo2"]),
        Detail("산소 투여", "예" if i["on_oxygen"] else "아니오", pts["oxygen"]),
        Detail("수축기 혈압", f"{i['sbp']:g} mmHg", pts["sbp"]),
        Detail("심박수", f"{i['hr']:g}/분", pts["hr"]),
        Detail("의식", "Alert" if i["consciousness"] == "alert" else "CVPU / 새로 생긴 혼돈", pts["consciousness"]),
        Detail("체온", f"{i['temp_c']:g} ℃", pts["temp"]),
    ]
    notes = ["관찰 빈도(RCP 2017): 0점 12시간 · 1-4점 4-6시간 · 한 항목 3점 또는 5-6점 1시간 · ≥7점 지속 감시.",
             "SpO₂ 척도 2는 고탄산혈증 호흡부전(목표 88-92%)으로 확인된 환자에게만 씁니다."]
    return Result(value=total, unit="점", label=label, severity=sev, details=details, notes=notes,
                  extra={"points": pts, "single_parameter_3": single3})


SPEC = register(CalculatorSpec(
    id="news2", name="NEWS2", group="조기경고",
    description="병동 환자 악화 조기경고 점수",
    inputs=(
        InputSpec("rr", "호흡수", "number", unit="/분", minimum=0, maximum=100, variable="rr"),
        InputSpec("spo2", "SpO₂", "number", unit="%", minimum=50, maximum=100, variable="spo2"),
        InputSpec("spo2_scale", "SpO₂ 척도", "select", default="1",
                  options=(Option("1", "척도 1 (일반)"), Option("2", "척도 2 (고탄산혈증 호흡부전, 목표 88-92%)"))),
        InputSpec("on_oxygen", "산소 투여 중", "boolean", default=False, derive=derive_on_oxygen, help="FiO₂ 기록이 있으면 0.21 초과일 때 자동 체크"),
        InputSpec("sbp", "수축기 혈압", "number", unit="mmHg", minimum=20, maximum=300, variable="sbp"),
        InputSpec("hr", "심박수", "number", unit="/분", minimum=0, maximum=300, variable="hr"),
        InputSpec("consciousness", "의식", "select", default="alert", derive=derive_consciousness,
                  options=(Option("alert", "Alert (명료)"), Option("cvpu", "CVPU - 혼돈·음성/통증 반응·무반응")),
                  help="GCS 기록이 있으면 15 미만일 때 CVPU 로 제안"),
        InputSpec("temp_c", "체온", "number", unit="℃", minimum=25, maximum=45, variable="temp_c"),
    ),
    compute=compute,
    references=("Royal College of Physicians. National Early Warning Score (NEWS) 2. 2017.",),
    scale=Scale(0, 20, (Band(5, "저위험", "ok"), Band(7, "중간", "warn"), Band(None, "고위험", "danger")),
                note="합계가 4점 이하여도 한 항목이 3점이면 저-중간 위험으로 긴급 평가 대상입니다."),
    guide="활력징후 6가지와 산소 투여 여부로 병동 환자의 악화를 조기에 잡는 점수. 5점 이상이면 긴급 평가, 7점 이상이면 응급 대응입니다.",
))
