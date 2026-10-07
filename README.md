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

오류 전달: Patient 404 → 404, snuh-fhir 503 → 503, 그 외 연결 문제 → 502.
**PAT 문제는 424 + `{"detail": {"code", "message"}}`** 로 구분해 돌려준다 — `pat_missing`(토큰 없음) · `pat_invalid`(snuh-fhir 401:
형식·폐기·만료) · `pat_no_access`(snuh-fhir 403: 소유자에게 FHIR 접근 허용 없음). 401/403 을 그대로 내지 않는 이유는 상위 gateway 가
계산기 자체의 로그인 문제로 오해해 가로챌 수 있어서다.

### 인증 — 서비스 계정 PAT (기본) / 사용자 본인 PAT (대체)

snuh-fhir 의 FHIR 호출에는 개인 액세스 토큰(PAT)이 필요하다. 계산기는 두 가지를 지원한다.

| 방식 | 설정 | 동작 |
| --- | --- | --- |
| **서비스 계정 PAT (기본)** | `APP_FHIR_TOKEN` 에 관리자가 발급한 토큰 | 모든 사용자가 그 토큰으로 조회. 화면에 PAT 패널이 뜨지 않고 상단에 「FHIR 연결됨」 표시. snuh-fhir 감사에는 서비스 계정이 남는다 |
| 사용자 본인 PAT (대체) | `APP_FHIR_TOKEN` 비움 | 화면 상단 「PAT」 패널에 본인 토큰 등록 → 요청 헤더 `X-Fhir-Token` 으로 전달. 탭 메모리·sessionStorage 에만 보관 |

요청에 `X-Fhir-Token` 이 있으면 항상 그 토큰이 서비스 토큰보다 우선한다. `GET /api/health/ready` 의 `token` 필드(`service`|`none`)로 어느 모드인지 알 수 있다.
서비스 계정 토큰의 소유 계정에는 snuh-fhir 관리자가 **FHIR 접근 허용**을 부여해야 하고, 만료(최대 365일) 전에 교체한다. mock 모드는 토큰이 필요 없다.

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

**먼저 `.env` 를 만든다.** 저장소 루트의 `.env` 를 백엔드가 기동 시 자동으로 읽는다 (셸에서 직접 지정한 값이 우선).
`.env` 없이 띄우면 기본 `APP_FHIR_MODE=http` 로 `localhost:8000` 의 snuh-fhir 에 붙으려다 **502** 가 난다.

```bash
cp .env.example .env
# .env 에서 아래 한 줄만 바꾼다
#   APP_FHIR_MODE=mock
```

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

mock 환자 (`backend/fixtures/patients/`):

| 환자번호 | 프로필 | 보여주는 것 |
| --- | --- | --- |
| `10000001` | 68세 남, 간경변·CKD·AF·뇌경색 병력, Cr 1.8 | Child-Pugh B · MELD-Na · CHA₂DS₂-VASc 5 · HAS-BLED 4. FiO₂ 가 없어 SOFA/APACHE II 는 「입력 필요」 |
| `20000002` | 77세 여, 폐렴·CHF·AF·COPD, FiO₂ 0.35 산소요법 | CURB-65 4 · SOFA·APACHE II 자동 계산 · 3개월 체중감소 6.8% → NRS 제안 |

새 환자를 추가하려면 같은 형식(Bundle collection, Patient·Observation·Condition)의 파일을 넣는다 — 서버 재시작 불필요.

### Docker (단일 호스트)

```bash
cp .env.example .env     # APP_FHIR_MODE=http, APP_FHIR_BASE_URL, APP_PATH_PREFIX 편집 (APP_FHIR_TOKEN 은 비움)
docker compose up -d --build
# http://localhost:8010/  → /ui/ 로 리다이렉트. 화면에서 본인 PAT 등록 후 조회
```

### 원내망(폐쇄망 k3s) 배포 — snuh-fhir 와 같은 방식

snuh-fhir 가 올라간 방식(멀티스테이지 이미지 → `docker save` tar 반입 → `k3s ctr images import` → k3s `platform` 네임스페이스 →
상위 gateway `/apps/runtime/<앱>/**` 라우트)을 그대로 따른다. 참고 파일: [`deploy/k8s.yaml`](deploy/k8s.yaml), [`deploy/build-and-save.sh`](deploy/build-and-save.sh).

1. **반출측(인터넷 되는 PC)에서 이미지 빌드·저장** — 프런트 빌드에 `node:24-alpine` 이 필요하다.
   ```bash
   sh deploy/build-and-save.sh 0.1.0        # dist/snuh-patient-calculator-0.1.0.tar
   ```
2. **반입** — snuh-fhir 와 같은 경로(이미지 tar 반입 절차)로 tar 를 원내망에 옮긴다. 매니페스트(`deploy/k8s.yaml`)는 ArgoCD 가 보는 배포 저장소에 넣는다.
3. **노드에서 이미지 import** — `sudo k3s ctr images import snuh-patient-calculator-0.1.0.tar`. 노드가 여러 대면 import 한 노드로 `nodeName` 을 고정하거나 모든 노드에 import 한다 (`imagePullPolicy: Never`).
4. **설정** — ConfigMap `calculator-config`: `APP_FHIR_MODE=http`, `APP_FHIR_BASE_URL=http://fhir.platform.svc.cluster.local:8000`(클러스터 내부 주소, gateway·TLS 우회), `APP_PATH_PREFIX=/apps/runtime/calculator`. 서비스 계정 토큰은 두지 않는다. PVC 불필요(상태 저장 없음).
5. **gateway 라우트 등록** — snuhai 상위 gateway(`gateway.tb_route`)에 `path=/apps/runtime/calculator/**`, `authentication=Y`. strip_prefix 여부와 무관하게 동작한다. 진입 URL 은 `https://<host>/apps/runtime/calculator/` → `/ui/` 리다이렉트.
6. **사용자 준비** — 각 사용자는 snuh-fhir 「내 토큰」(`https://<host>/apps/runtime/fhir/ui/`)에서 PAT 를 발급받고, snuh-fhir 관리자가 그 사용자에게 **FHIR 접근 허용**을 부여해야 한다. 계산기 화면의 PAT 패널에는 같은 gateway 아래의 snuh-fhir 「내 토큰」 링크가 자동으로 뜬다.
7. **확인** — `kubectl -n platform rollout status deploy/calculator`, `/apps/runtime/calculator/api/health` 200, `/api/health/ready` 가 `{"fhir":"ok"}`. 첫 사용자 시험: PAT 등록 → 실환자 조회 → 좌측 「가져온 값」에서 빠진 항목 확인 → 필요하면 ConfigMap `calculator-variables` 로 별칭 보강 후 재기동.

운영 매니페스트 저장소·tar 반입 포털의 실제 위치는 snuh-fhir 배포 담당(#71 체크리스트)과 같다.

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
