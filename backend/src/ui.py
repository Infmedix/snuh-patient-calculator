"""프런트(빌드된 dist)를 `/ui` 로 서빙 + `/` → `./ui/` 307 (snuh-fhir `src/ui.py` 이식).

- 프런트는 `vite base:"./"` + 상대 경로 API(`../api/...`) 라 prefix 를 모른 채 동작한다.
- `/` 의 Location 은 **상대** `./ui/` - strip 하는 gateway 뒤에서도 prefix 가 유지된다.
- dist 가 없으면 부팅이 죽지 않고 `/ui` 만 404 (백엔드 단독 배포·테스트 보호).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from src import settings

UI_MOUNT_PATH = "/ui"
_state = {"dist": None}


class UiStaticFiles(StaticFiles):
    """index.html 은 항상 재검증(no-cache) - 새 배포 뒤 브라우저가 옛 index.html 로 옛 번들을 불러오는 것을 막는다.
    해시가 붙은 assets/ 는 내용이 바뀌면 이름도 바뀌므로 오래 캐시해도 안전하다."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        # Starlette 는 os.path.normpath 를 거친 경로를 준다 - Windows 에서는 구분자가 백슬래시
        if path.replace("\\", "/").startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


def install_ui(app: FastAPI, dist_dir: Optional[str] = None) -> bool:
    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="./ui/", status_code=307)

    dist = Path(dist_dir if dist_dir is not None else settings.UI_DIST_DIR)
    if not dist.is_dir() or not (dist / "index.html").is_file():
        _state["dist"] = None
        return False
    app.mount(UI_MOUNT_PATH, UiStaticFiles(directory=str(dist), html=True), name="ui")
    _state["dist"] = str(dist)
    return True


def describe() -> str:
    if _state["dist"]:
        return f"mounted ({UI_MOUNT_PATH} ← {_state['dist']})"
    return f"not mounted (dist 없음: {settings.UI_DIST_DIR} - {UI_MOUNT_PATH} 는 404)"
