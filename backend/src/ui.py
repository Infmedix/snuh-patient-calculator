"""프런트(빌드된 dist)를 `/ui` 로 서빙 + `/` → `./ui/` 307 (snuh-fhir `src/ui.py` 이식).

- 프런트는 `vite base:"./"` + 상대 경로 API(`../api/...`) 라 prefix 를 모른 채 동작한다.
- `/` 의 Location 은 **상대** `./ui/` — strip 하는 gateway 뒤에서도 prefix 가 유지된다.
- dist 가 없으면 부팅이 죽지 않고 `/ui` 만 404 (백엔드 단독 배포·테스트 보호).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src import settings

UI_MOUNT_PATH = "/ui"
_state = {"dist": None}


def install_ui(app: FastAPI, dist_dir: Optional[str] = None) -> bool:
    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="./ui/", status_code=307)

    dist = Path(dist_dir if dist_dir is not None else settings.UI_DIST_DIR)
    if not dist.is_dir() or not (dist / "index.html").is_file():
        _state["dist"] = None
        return False
    app.mount(UI_MOUNT_PATH, StaticFiles(directory=str(dist), html=True), name="ui")
    _state["dist"] = str(dist)
    return True


def describe() -> str:
    if _state["dist"]:
        return f"mounted ({UI_MOUNT_PATH} ← {_state['dist']})"
    return f"not mounted (dist 없음: {settings.UI_DIST_DIR} — {UI_MOUNT_PATH} 는 404)"
