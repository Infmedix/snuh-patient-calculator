"""계산기 레지스트리 — import 순서가 화면 표시 순서다 (그룹별).

새 계산기를 추가하면 여기에 import 를 추가하고 tests/test_calculators.py 의 순서 테스트를 갱신한다.
"""

from src.calculators.base import CalculatorSpec, InputError, Result, all_specs, get  # noqa: F401

# 신체·신장
from src.calculators import bmi, egfr, crcl  # noqa: E402,F401
# 심혈관
from src.calculators import cha2ds2_vasc, has_bled, qtc  # noqa: E402,F401
# 간
from src.calculators import child_pugh, meld_na  # noqa: E402,F401
# 중증도
from src.calculators import curb65, sofa, apache2  # noqa: E402,F401
# 영양
from src.calculators import nrs2002  # noqa: E402,F401

__all__ = ["CalculatorSpec", "InputError", "Result", "all_specs", "get"]
