# SNUH 환자 계산기 (snuh-patient-calculator)

환자번호를 입력하면 [snuh-fhir](../snuh-fhir) API 에서 **가장 최근** 검사·활력징후·심전도·진단을 가져와
12종 임상 계산기의 입력을 자동으로 채우고 결과를 보여주는 snuhai 플랫폼용 서비스.

| 그룹 | 계산기 |
| --- | --- |
| 신체·신장 | BMI · eGFR (CKD-EPI 2021) · CrCl (Cockcroft-Gault) |
| 심혈관 | CHA₂DS₂-VASc · HAS-BLED · QTc (Bazett/Fridericia/Framingham/Hodges) |
| 간 | Child-Pugh · MELD-Na (UNOS 2016) |
| 중증도 | CURB-65 · SOFA · APACHE II |
| 영양 | NRS-2002 |

자동으로 채운 값은 **출처(항목명·기록 시각)** 를 함께 표시하고, 사용자가 언제든 수정할 수 있다.
복수·뇌병증·의식 혼미·투약·혈압상승제 같은 진찰·처방 정보는 직접 입력한다. 환자 없이 수동 계산도 된다.

설계 문서: [`docs/superpowers/specs/2026-10-07-patient-calculator-design.md`](docs/superpowers/specs/2026-10-07-patient-calculator-design.md)

## 구조

```
backend/            FastAPI (Python 3.11)
  main.py
  src/calculators/  계산기 12종 — 입력 스펙 + 순수 계산 함수 (프런트 폼은 스펙으로 렌더링)
  src/snapshot/     FHIR 번들 → 정규 변수 최신값 (variables.py 별칭 사전, flags.py KCD 접두 플래그)
  src/fhir/         snuh-fhir HTTP 클라이언트 + mock(fixture) 클라이언트
  src/prefill.py    스냅샷 → 계산기별 자동 채움 + 개요
  fixtures/         mock 모드 환자 번들 (patients/{환자번호}.json)
frontend/           Vite + React 19 + Tailwind 4 (snuh-fhir 프런트와 같은 스택·규칙)
Dockerfile          base / frontend / dev / prod 스테이지 (snuh-fhir 와 동일 구조)
```

데이터 경로는 snuh-fhir API 만 쓴다 (ODS 직접 접근 없음). FHIR 호출에는 `Authorization: Bearer <PAT>` 가 필요하다.

## API

| 메서드·경로 | 설명 |
| --- | --- |
| `GET /api/health` | liveness (외부 왕복 없음) |
| `GET /api/health/ready` | snuh-fhir `/health` 왕복. 실패 503 |
| `GET /api/calculators` | 계산기 스펙 목록 + 변수·플래그 라벨 |
| `GET /api/patients/{환자번호}/snapshot` | 변수별 최근값 · 체중 이력 · 진단 플래그 · 경고 |
| `GET /api/patients/{환자번호}/overview` | 스냅샷 + 계산기별 자동 채움(출처 포함) + 계산 가능한 결과 |
| `POST /api/calculate/{calc_id}` `{"inputs": {...}}` | 단건 계산. 필수 누락·형식 오류는 400 `{"detail": {"message", "missing", "invalid"}}` |

오류 전달: snuh-fhir 401/403 → **502** (이 서비스의 토큰·권한 설정 문제), 503 → 503, Patient 404 → 404.
요청 헤더 `X-Fhir-Token` 이 있으면 서비스 계정 PAT 대신 그 토큰으로 snuh-fhir 를 호출한다.

## 환자 1명을 조회할 때 일어나는 일

| snuh-fhir 호출 | 기본 기간 | 쓰임 |
| --- | --- | --- |
| `GET /Patient/{id}` | — | 성별·생년월일(→ 나이) |
| `GET /Observation?category=laboratory&date=ge…` | 180일 (`APP_LAB_LOOKBACK_DAYS`) | 검사 수치 |
| `GET /Observation?category=clinical&date=ge…` | 100일 (`APP_WEIGHT_HISTORY_DAYS`, 활력징후 30일 포함) | 활력징후·체중·신장·GCS·소변량 |
| `GET /Observation?category=exam&code=심전도&date=ge…` | 365일 | QT·QTc·심박수 |
| `GET /Condition` | 전체 (최대 2페이지) | KCD 코드 → 진단 플래그 |

Patient 가 404 면 전체 404. 나머지 네 호출은 실패해도 **경고로 강등**하고 가져온 것만으로 진행한다
(Condition 실패 시 플래그는 "모름" 으로 두고 체크박스를 비워 둔다 — False 로 바꾸지 않는다).

### 항목명 → 변수 매핑 (중요)

검사항목명(`component.code.coding.display`)·간호어휘명·심전도 구성요소명을 **별칭 사전**으로 정규 변수에 매핑한다
(`backend/src/snapshot/variables.py`). 실제 ODS 항목명은 아직 확정되지 않았으므로, 운영에서 매칭이 안 되는 항목은
`APP_VARIABLE_MAP_PATH` 로 YAML 을 지정해 코드 수정 없이 별칭을 보강한다 — 예시 [`config/variables.example.yaml`](config/variables.example.yaml).

```yaml
creatinine:
  add_aliases: ["크레아티닌(혈청)"]
  add_exclude: ["cystatin"]
```

매칭 규칙: ASCII 4자 이하 별칭(`ast`, `k`)은 토큰 정확 일치, 그 외는 소문자 부분 문자열. `exclude` 토큰(`urine`, `direct` …)이
들어 있으면 매칭하지 않는다. 사전 순서대로 첫 매칭을 쓴다.

단위 정규화: 혈소판·백혈구가 `/µL` 로 1만 이상이면 ×10³/µL 로 환산, 크레아티닌·빌리루빈 µmol/L → mg/dL, 알부민 g/L → g/dL,
FiO₂ 퍼센트 → 분율. 그 외 단위는 그대로 믿고 화면에 표시한다.

### 진단 플래그 (KCD 접두)

고혈압 I10–I15 · 당뇨 E10–E14 · 심부전 I50, I11.0, I13.0, I13.2 · 뇌졸중/TIA I60–I64, G45, G46 · 혈관질환 I21, I22, I25, I70, I71, I73.9 ·
심방세동 I48 · 출혈 병력 K92.0–2, I60–I62, D68, D69, R58 · 만성 신질환 N18, N19, Z99.2, Z94.0 · 만성 간질환 K70–K77 · 악성 종양 C00–C97.
플래그는 **제안값**이고 화면에서 뒤집을 수 있다.

## 실행

### 로컬 개발 (mock 데이터, snuh-fhir 불필요)

```bash
# 백엔드 — uv (Python 3.11+)
cd backend
uv sync
APP_FHIR_MODE=mock uv run uvicorn main:app --port 8010 --no-access-log

# 프런트 — vite dev 서버 (API 는 :8010 으로 proxy)
cd frontend
npm ci
VITE_API_PROXY=http://localhost:8010 npm run dev     # http://localhost:5174
```

mock 환자: `10000001` (`backend/fixtures/patients/10000001.json`). 새 환자를 추가하려면 같은 형식(Bundle collection)의 파일을 넣는다.

### Docker (운영)

```bash
cp .env.example .env     # APP_FHIR_BASE_URL, APP_FHIR_TOKEN, APP_PATH_PREFIX 편집
docker compose up -d --build
# http://localhost:8010/  → /ui/ 로 리다이렉트
```

`APP_FHIR_TOKEN` 은 snuh-fhir 「내 토큰」에서 발급한 PAT 이며, 관리자가 그 사용자에게 **FHIR 접근 허용**을 부여해야 호출이 된다 (아니면 403 → 이 서비스는 502 로 전달).

### 테스트

```bash
cd backend && uv run pytest -q                      # 계산기·스냅샷·API (mock)
docker compose --profile dev run --rm dev            # 같은 테스트를 컨테이너에서
cd frontend && npm test                              # vitest
```

## 환경변수

`.env.example` 참고. 핵심: `APP_FHIR_MODE`(http|mock) · `APP_FHIR_BASE_URL` · `APP_FHIR_TOKEN` · `APP_*_LOOKBACK_DAYS` ·
`APP_VARIABLE_MAP_PATH` · `APP_PATH_PREFIX` · `APP_UI_DIST_DIR`.

## 임상 참고

- 계산식과 분류 기준의 출전은 각 `backend/src/calculators/*.py` docstring 에 적혀 있다 (CKD-EPI 2021, UNOS 2016 MELD, Vincent 1996 SOFA, Knaus 1985 APACHE II 등).
- SOFA·APACHE II 는 「24시간 최악값」기준인데 자동 채움은 **최근 1건**이다 — 화면에 안내 문구를 둔다.
- 결과는 임상 판단 보조용이며 저장·이력 기능은 없다.
