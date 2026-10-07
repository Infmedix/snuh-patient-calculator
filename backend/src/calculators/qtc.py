"""QTc - 심박수 보정 QT 간격.

RR(초) = 60 / HR.  Bazett QT/√RR · Fridericia QT/∛RR · Framingham QT + 154(1−RR) · Hodges QT + 1.75(HR−60).
대표값은 Fridericia (빈맥·서맥에서 Bazett 의 과대/과소 보정이 덜함 - AHA/ACC/HRS 2009 권고 중 하나).
연장 기준: 남 >450 ms, 여 >460 ms; ≥500 ms 는 TdP 위험 증가. Rautaharju PM et al. Circulation 2009;119:e241-50.
"""

from __future__ import annotations

from src.calculators.base import Band, CalculatorSpec, Detail, InputSpec, Result, Scale, register
from src.calculators.common import derive_ecg_or_vital_hr, sex_input


def formulas(qt_ms: float, hr: float) -> dict[str, float]:
    rr = 60.0 / hr
    return {
        "bazett": qt_ms / rr ** 0.5,
        "fridericia": qt_ms / rr ** (1 / 3),
        "framingham": qt_ms + 154 * (1 - rr),
        "hodges": qt_ms + 1.75 * (hr - 60),
    }


def compute(i: dict) -> Result:
    f = formulas(i["qt_ms"], i["hr"])
    qtc = f["fridericia"]
    limit = 460 if i["sex"] == "F" else 450
    if qtc >= 500:
        label, sev = "QTc ≥500 ms - 심각한 연장 (TdP 위험)", "danger"
    elif qtc > limit:
        label, sev = f"QTc 연장 (>{limit} ms)", "warn"
    elif qtc < 340:
        label, sev = "QTc 단축 (<340 ms)", "warn"
    else:
        label, sev = "정상 범위", "ok"
    details = [
        Detail("Fridericia (대표)", f"{f['fridericia']:.0f} ms"),
        Detail("Bazett", f"{f['bazett']:.0f} ms"),
        Detail("Framingham", f"{f['framingham']:.0f} ms"),
        Detail("Hodges", f"{f['hodges']:.0f} ms"),
        Detail("입력", f"QT {i['qt_ms']:g} ms · HR {i['hr']:g}/분 · {'여' if i['sex']=='F' else '남'}"),
    ]
    notes = ["QRS 가 넓으면(≥120 ms, 각차단·심실조율) QTc 해석에 보정이 필요합니다."]
    if i.get("reported_qtc_ms") is not None:
        details.append(Detail("기기 보고 QTc", f"{i['reported_qtc_ms']:g} ms"))
        if abs(i["reported_qtc_ms"] - f["bazett"]) > 20 and abs(i["reported_qtc_ms"] - qtc) > 20:
            notes.append("기기 보고 QTc 와 계산값 차이가 20 ms 를 넘습니다 - 입력 QT/HR 이 같은 기록인지 확인하세요.")
    return Result(value=round(qtc), unit="ms", label=label, severity=sev, details=details, notes=notes,
                  extra={k: round(v, 1) for k, v in f.items()})


SPEC = register(CalculatorSpec(
    id="qtc", name="QTc", group="심혈관",
    description="심전도 QT 간격의 심박수 보정",
    inputs=(
        InputSpec("qt_ms", "QT 간격", "number", unit="ms", minimum=100, maximum=1000, variable="qt_ms"),
        InputSpec("hr", "심박수", "number", unit="/분", minimum=20, maximum=300, derive=derive_ecg_or_vital_hr),
        sex_input(),
        InputSpec("reported_qtc_ms", "기기 보고 QTc (참고)", "number", unit="ms", minimum=100, maximum=1000,
                  required=False, variable="qtc_ms"),
    ),
    compute=compute,
    references=("Rautaharju PM et al. AHA/ACCF/HRS. Circulation 2009;119:e241-50.",),
    scale=Scale(300, 600, (Band(340, "단축", "warn"), Band(450, "정상", "ok"), Band(500, "연장", "warn"), Band(None, "고위험", "danger")),
                note="연장 기준: 남 >450 ms, 여 >460 ms. 500 ms 이상은 torsades de pointes 위험이 뚜렷이 올라갑니다."),
    guide="심박수가 빠르거나 느리면 QT 가 달라지므로 60회/분 기준으로 보정한 값. 대표값은 Fridericia 식이며 네 가지 식을 모두 보여줍니다.",
))
