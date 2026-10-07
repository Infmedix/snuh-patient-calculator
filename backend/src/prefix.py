"""배포 prefix 수용 ASGI 미들웨어 — snuh-fhir `src/prefix.py` 이식 (auth-9 #76).

gateway 가 prefix 를 strip 하는 배치와 하지 않는 배치 양쪽에서 동작한다: `scope["path"]` 에 prefix 를
보장하고 `scope["root_path"]` 를 prefix 로 둔다 (Starlette 라우팅은 path 에서 root_path 를 떼어 매칭).
prefix 자체(슬래시 없음) → `prefix/` 307. `X-Forwarded-Prefix` 는 보지 않는다 (env 단일 출처).
"""

from __future__ import annotations

from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send

from src import settings


def normalize_prefix(raw: Optional[str]) -> str:
    value = (raw or "").strip().strip("/")
    return f"/{value}" if value else ""


def route_path(scope: Scope) -> str:
    path: str = scope.get("path", "")
    root_path: str = scope.get("root_path", "")
    if not root_path or not path.startswith(root_path):
        return path
    if path == root_path:
        return ""
    if path[len(root_path)] == "/":
        return path[len(root_path):]
    return path


class PrefixAliasMiddleware:
    def __init__(self, app: ASGIApp, prefix: Optional[str] = None):
        self._app = app
        self._prefix = prefix   # None = 호출 시점에 settings 를 읽는다 (테스트 monkeypatch)

    @property
    def prefix(self) -> str:
        return normalize_prefix(self._prefix if self._prefix is not None else settings.PATH_PREFIX)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        prefix = self.prefix
        if not prefix or scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if scope["type"] == "http" and path == prefix:
            query = scope.get("query_string") or b""
            location = f"{prefix}/".encode("latin-1") + (b"?" + query if query else b"")
            await send({"type": "http.response.start", "status": 307,
                        "headers": [(b"location", location), (b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            return
        scope = dict(scope)
        if not path.startswith(prefix + "/"):
            scope["path"] = prefix + path
            if scope.get("raw_path") is not None:
                scope["raw_path"] = prefix.encode("latin-1") + scope["raw_path"]
        scope["root_path"] = prefix
        await self._app(scope, receive, send)
