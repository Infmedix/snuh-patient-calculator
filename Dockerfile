FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

EXPOSE 8000
ENV APP_LOG_LEVEL=INFO


# 프런트 빌드 스테이지 — base 와 독립. `--target dev` 는 이 스테이지를 빌드하지 않는다.
FROM node:24-alpine AS frontend

WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# 개발/테스트 이미지 — 테스트 의존성 포함. 테스트는 이 스테이지에서 돌린다 (mock 데이터, 외부 접속 없음).
FROM base AS dev

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

WORKDIR /app/backend
ENTRYPOINT []
CMD ["pytest", "-q"]


# 운영 이미지. **반드시 마지막 스테이지** — `--target` 없는 build 가 마지막 스테이지를 만든다.
FROM base AS prod

# 빌드된 프런트 — backend/ 기준 ../frontend/dist (settings.UI_DIST_DIR 기본값)
COPY --from=frontend /fe/dist ./frontend/dist

WORKDIR /app/backend
# --no-access-log: 경로의 환자번호가 stdout 에 남지 않게 (main.py 의 로거 차단과 이중 방어)
# 포트: APP_PORT > PORT(snuhai 앱 스토어가 주입, 기본 8080) > 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-${PORT:-8000}} --no-access-log"]
