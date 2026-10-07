"""환자 스냅샷 - FHIR 번들에서 뽑아낸 「변수별 가장 최근 값」과 진단 플래그.

계산기 prefill 과 API 응답이 같은 모델을 쓴다. 값마다 출처(항목명·리소스 id·카테고리)와
기록 시각을 보존한다 - 화면은 이걸로 「FHIR · 10-01 · Creatinine」 태그를 그린다.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Sex = Literal["M", "F"]


class Source(BaseModel):
    display: str                      # 원 항목명 (검사항목명·간호어휘명·심전도 구성요소명)
    category: str                     # laboratory | clinical | exam | patient | derived
    resource_id: Optional[str] = None  # 검체번호·기록 ID·처방 ID


class ObservedValue(BaseModel):
    variable: str
    value: float
    unit: Optional[str] = None
    observed_at: Optional[str] = None  # ISO8601 (서버가 준 그대로, 보통 KST naive)
    source: Source
    derived: bool = False              # 다른 값에서 계산 (예: MAP = (SBP+2DBP)/3)


class WeightPoint(BaseModel):
    value: float
    observed_at: str


class PatientInfo(BaseModel):
    id: str
    name: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None


class ConditionItem(BaseModel):
    code: str
    display: Optional[str] = None
    recorded_date: Optional[str] = None


class FlagEvidence(BaseModel):
    present: bool
    codes: list[str] = Field(default_factory=list)
    displays: list[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    patient: PatientInfo
    fetched_at: str
    values: dict[str, ObservedValue] = Field(default_factory=dict)
    weight_history: list[WeightPoint] = Field(default_factory=list)   # 최신순
    conditions: list[ConditionItem] = Field(default_factory=list)      # 코드 중복 제거, 최신순
    conditions_available: bool = True                                  # Condition 호출 실패 시 False
    flags: dict[str, FlagEvidence] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    # ----- prefill 편의 -----

    def value(self, variable: str) -> Optional[ObservedValue]:
        return self.values.get(variable)

    def num(self, variable: str) -> Optional[float]:
        v = self.values.get(variable)
        return v.value if v else None

    def flag(self, name: str) -> Optional[bool]:
        """진단 플래그. Condition 을 못 가져왔으면 None (모른다) - False 와 구분한다."""
        if not self.conditions_available:
            return None
        f = self.flags.get(name)
        return bool(f and f.present)
