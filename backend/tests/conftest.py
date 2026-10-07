import sys
from pathlib import Path

# `import src...`, `import main` 이 backend/ 기준으로 풀리게 (uv run / 호스트 pytest 모두)
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
