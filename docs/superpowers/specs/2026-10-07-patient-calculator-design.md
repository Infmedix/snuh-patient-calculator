# SNUH 환자 정보 기반 수치 계산기 — 설계

작성일: 2026-10-07. snuhai 플랫폼에 올라가는 독립 서비스. 참고 구현: `snuh-fhir`
(FastAPI 백엔드 + Vite/React 19/Tailwind 4 프런트, `/ui` 정적 서빙, 배포 prefix, PAT Bearer).

> 이 문서는 자율 실행 모드에서 작성됐다. 사용자에게 확인하지 못한 결정은 「가정」으로 표시했다.
> 가정이 틀리면 해당 절만 고치면 되도록 경계를 나눴다.

## 1. 목표

- 환자번호를 입력하면 snuh-fhir API 에서 **가장 최근 정보**(인구학·검사·활력징후·심전도·진단)를 가져와
  12종 계산기의 입력을 자동으로 채우고 결과를 보여준다.
- 자동으로 채울 수 없는 항목(복수·뇌병증·의식 혼미·투약 등)은 사용자가 직접 입력한다. 자동 채움값도 수정 가능.
- 환자 없이 수동 계산도 된다.
- 어떤 값이 어디서(검사항목명·기록일시) 왔는지 **출처를 항상 표시**한다 — 임상 판단 보조 도구이므로 근거 추적이 필수.

계산기 목록: BMI, eGFR(CKD-EPI 2021), CrCl(Cockcroft-Gault), CHA₂DS₂-VASc, HAS-BLED, Child-Pugh,
MELD-Na, CURB-65, SOFA, APACHE II, QTc, NRS-2002.

## 2. 아키텍처

```
브라우저(React SPA, /ui/)
   │  ../api/...  (문서 기준 상대 경로 — prefix 무관)
   ▼
calculator backend (FastAPI)
   ├─ calculators/   순수 계산 함수 + 입력 스펙 (프런트 폼은 이 스펙으로 렌더링)
   ├─ fhir/          snuh-fhir HTTP 클라이언트 (httpx, 동시 호출, 실패는 경고로 강등)
   ├─ snapshot/      FHIR 번들 → 정규 변수(creatinine, sbp, …) 최신값 + 진단 플래그 추출
   └─ prefill        스냅샷 → 계산기별 입력 자동 채움(출처 포함)
   │  Authorization: Bearer <PAT>
   ▼
snuh-fhir  (/apps/runtime/fhir)  → ODS
```

- **DB 직접 접근 없음.** 데이터 경로는 snuh-fhir API 만 (data_extract 와 같은 원칙).
- 백엔드가 계산을 담당한다 (프런트 중복 구현 금지). 프런트는 스펙 기반 폼 + 결과 표시.
- 개발·시연용 **mock 모드**: `APP_FHIR_MODE=mock` 이면 `backend/fixtures/` 의 번들을 읽는다.

### 가정 A — 인증
서비스 계정 PAT 를 env(`APP_FHIR_TOKEN`)로 주입한다. 요청에 `X-Fhir-Token` 헤더가 있으면 그 값을 우선
전달한다(사용자 개인 PAT 로 호출하고 싶은 배포 대응). 토큰은 로그·URL 에 남기지 않는다.

### 가정 B — 배포 경로
`APP_PATH_PREFIX`(예: `/apps/runtime/calculator`) 를 snuh-fhir 와 같은 방식(ASGI 미들웨어)으로 수용한다.
프런트는 `base:"./"` + 상대 API 경로라 prefix 를 모른다.

## 3. 데이터 추출 (snapshot)

환자번호 `pid` 에 대해 다음을 **동시에** 호출한다. 각 호출 실패는 `warnings` 로 강등하고 나머지는 계속한다.
Patient 404 만 전체 404.

| 호출 | 기간(기본) | 쓰임 |
| --- | --- | --- |
| `GET /Patient/{pid}` | — | 성별·생년월일(→ 나이)·이름 |
| `GET /Observation?patient=&category=laboratory&date=ge{오늘-180일}&_count=1000` (최대 3페이지) | `APP_LAB_LOOKBACK_DAYS=180` | 검사 수치 |
| `GET /Observation?patient=&category=clinical&date=ge{오늘-30일}&_count=1000` (최대 3페이지) | `APP_VITAL_LOOKBACK_DAYS=30` | 활력징후·체중·신장·GCS·소변량 |
| `GET /Observation?patient=&category=exam&code=심전도&date=ge{오늘-365일}&_count=200` | `APP_ECG_LOOKBACK_DAYS=365` | QT·QTc·심박수 |
| `GET /Condition?patient=&_count=1000` (최대 2페이지, 기본 최신순) | — | KCD 코드 → 진단 플래그 |

### 변수 매핑 (가정 C — 실제 항목명 미확인)
검사항목명(laboratory `component.code.coding.display`), 간호항목명/어휘명(clinical `code.coding.display`,
`valueCodeableConcept.coding.display`), 심전도 구성요소명(exam `component.code.coding.display`)을
**별칭 목록(소문자 부분일치, 2글자 이하 별칭은 정확일치)** 으로 정규 변수에 매핑한다.
기본 별칭은 `backend/src/snapshot/variables.py` 에 두고, 운영 항목명이 다르면
`APP_VARIABLE_MAP_PATH`(YAML) 로 **코드 수정 없이 덮어쓸 수 있게** 한다. discharge-note 의 별칭 규칙(백혈구/혈색소/혈소판/크레아티닌 …)을 출발점으로 쓴다.

정규 변수: `weight_kg height_cm sbp dbp map hr rr temp_c spo2 gcs urine_output_24h fio2 pao2 paco2 ph hco3
creatinine bun sodium potassium bilirubin_total albumin inr platelets wbc hematocrit ast alt alp
qt_ms qtc_ms ecg_hr` + Patient 의 `age sex`.

변수별 **가장 최근 1건**(`effectiveDateTime` 기준)을 고르고 `{value, unit, observed_at, source{display, resource_id, category}}` 로 보존한다. 체중은 1·2·3개월 전 값도 함께 보존해 NRS-2002 체중감소율에 쓴다.
값 문자열은 `<0.1`, `>500`, `1,234` 형태를 허용해 숫자만 취하고, 숫자가 아니면 버린다(경고 기록).
단위 정규화: 혈소판·백혈구가 `/uL` 단위로 1만 이상이면 ×10³/µL 로 환산. 그 외는 입력 단위를 그대로 믿고 화면에 단위를 표시한다.

### 진단 플래그 (KCD 접두)
Condition 의 `code.coding.code` 를 중복 제거 후 접두 매칭. `verificationStatus=entered-in-error` 는 서버 기본 제외라 별도 처리 없음.

| 플래그 | KCD/ICD-10 접두 | 쓰는 계산기 |
| --- | --- | --- |
| hypertension | I10–I15 | CHA₂DS₂-VASc, HAS-BLED |
| diabetes | E10–E14 | CHA₂DS₂-VASc |
| heart_failure | I50, I11.0, I13.0, I13.2 | CHA₂DS₂-VASc |
| stroke_tia | I60–I64, G45, G46 | CHA₂DS₂-VASc, HAS-BLED |
| vascular_disease | I21, I22, I25, I70, I71, I73.9 | CHA₂DS₂-VASc |
| atrial_fibrillation | I48 | (표시용) |
| bleeding_history | K92.0–K92.2, I60–I62, D68, D69, R58 | HAS-BLED |
| renal_disease | N18, N19, Z99.2, Z94.0 | HAS-BLED |
| liver_disease | K70–K77 | HAS-BLED, Child-Pugh(참고) |
| malignancy | C00–C97 | NRS-2002(참고) |

플래그는 **제안값**이다 — 화면에서 체크박스로 보이고 사용자가 뒤집을 수 있다.

## 4. 계산기 모듈

각 계산기는 `CalculatorSpec` 하나로 정의된다.

```python
@dataclass
class InputSpec:
    key: str; label: str; type: Literal["number","boolean","select"]
    unit: str | None = None; options: list[Option] | None = None
    required: bool = True; variable: str | None = None   # 스냅샷 정규 변수 (자동 채움)
    flag: str | None = None                               # 진단 플래그 (boolean 자동 채움)
    help: str | None = None

@dataclass
class CalculatorSpec:
    id: str; name: str; group: str; description: str
    inputs: list[InputSpec]
    compute: Callable[[dict], Result]       # 검증된 입력 → Result
    references: list[str]
```

`Result = {value, unit?, score?, label, severity("ok"|"warn"|"danger"|"info"), details: [{label, points|text}], notes: []}`.

계산식 (근거는 각 모듈 docstring 에 인용):
- **BMI** kg/m². 대한비만학회 2022 기준(저체중 <18.5 / 정상 18.5–22.9 / 비만전단계 23–24.9 / 1단계 25–29.9 / 2단계 30–34.9 / 3단계 ≥35).
- **eGFR** CKD-EPI 2021 (인종 변수 없음). 142·min(Scr/κ,1)^α·max(Scr/κ,1)^-1.200·0.9938^age·1.012(여). G1–G5 단계.
- **CrCl** Cockcroft-Gault, 체중 기준 선택(실제/이상/보정). 이상체중 Devine. 보정체중 = IBW + 0.4(실제−IBW).
- **CHA₂DS₂-VASc** 0–9. 여성 단독 1점은 해석 문구로 안내.
- **HAS-BLED** 0–9. 고혈압 항목은 SBP>160 자동, 신장이상은 Cr>2.26 mg/dL 또는 투석/이식 플래그, 간이상은 간질환 플래그 또는 빌리루빈>2×ULN(1.2) 과 AST/ALT/ALP>3×ULN 동시.
- **Child-Pugh** 5–15, A/B/C.
- **MELD-Na** UNOS 2016: 하한 1, Cr 상한 4(투석 시 4), MELD>11 이면 Na 보정(125–137 clamp), 최종 6–40.
- **CURB-65** BUN>19 mg/dL(≈urea>7 mmol/L), RR≥30, SBP<90 또는 DBP≤60, 나이≥65, 의식 혼미(수동).
- **SOFA** 6개 장기 0–4. 호흡은 PaO₂/FiO₂ 와 기계환기 여부, 심혈관은 MAP 또는 혈압상승제 단계(select), 신장은 Cr 또는 소변량.
- **APACHE II** APS 12항목 + 나이 + 만성건강. FiO₂≥0.5 면 A-aDO₂ = FiO₂·713 − PaCO₂/0.8 − PaO₂, 아니면 PaO₂. pH 없으면 HCO₃⁻. 급성신부전이면 Cr 점수 2배. GCS 는 15−GCS.
- **QTc** Bazett·Fridericia·Framingham·Hodges 모두 계산, 기본 표시는 Fridericia(빈맥·서맥에서 Bazett 왜곡). 남 >450 / 여 >460 ms 연장, ≥500 ms 고위험. HR 은 심전도 심박수 → 활력징후 HR 순으로 채움.
- **NRS-2002** 1차 스크리닝 4문항 + 최종(영양상태 0–3, 질병중증도 0–3, 70세 이상 +1). 체중감소율은 스냅샷 체중 이력에서 자동 제안.

## 5. API

| 메서드·경로 | 응답 |
| --- | --- |
| `GET /api/health` | `{"status":"ok"}` (liveness, FHIR 왕복 없음) |
| `GET /api/health/ready` | snuh-fhir `/health` 왕복. 실패 503 |
| `GET /api/calculators` | 계산기 스펙 목록 (입력 정의 포함) |
| `GET /api/patients/{pid}/snapshot` | 스냅샷 (환자·변수·플래그·경고) |
| `GET /api/patients/{pid}/overview` | 스냅샷 + 계산기별 `prefill`(입력값+출처) + 계산 가능한 것은 `result` |
| `POST /api/calculate/{calc_id}` `{"inputs":{…}}` | `Result`. 필수 누락은 400 `{"detail":..., "missing":[…]}` |

오류 전달: snuh-fhir 401/403 → 502 + 「FHIR 토큰/권한」 안내, 503 → 503 그대로, Patient 404 → 404.
개인정보: 환자번호는 access log 에 남지 않게 uvicorn access log 를 끈다(snuh-fhir 와 동일).

## 6. 프런트 (단일 화면)

- 상단: 환자번호 입력 + 불러오기. 로딩·오류 상태.
- 좌측 패널: 환자 요약(번호·성별·나이), 가져온 값 표(변수·값·단위·기록일시·출처), 7일 넘은 값은 amber 태그, 진단 플래그 칩.
- 본문: 계산기 카드 그리드. 그룹: 신체·신장 / 심혈관 / 간 / 중증도 / 영양.
  카드 = 결과(점수 + 해석 배지) + 입력 폼(스펙 기반 렌더링, 값마다 「FHIR · 10-01」 또는 「직접 입력」 태그) + 누락 안내.
  입력 변경 시 300 ms 디바운스 후 `POST /api/calculate/{id}` 재계산.
- 환자 없이도 카드는 비어 있는 폼으로 동작.
- 외부 UI 라이브러리 없음, Tailwind 만 (snuh-fhir `ui.tsx` 소품 이식).

## 7. 오류 처리·안전

- 계산기는 입력 범위를 검증한다(음수·0 나누기·비현실 값은 400 과 메시지).
- 자동 채움값이 오래되었거나(기간 상한 초과) 누락이면 결과를 내지 않고 「입력 필요」로 둔다 — 조용히 0 으로 채우지 않는다.
- 결과 하단에 고정 문구: 「임상 판단 보조용. 입력 출처와 기록 시점을 확인하세요.」

## 8. 테스트

- 백엔드(pytest): 계산기별 공개 예제값 검증(경계값 포함), 번들 fixture → 스냅샷 추출(별칭 매칭·최신값 선택·단위 환산·플래그), API 라우트(mock FHIR), prefix.
- 프런트(vitest): API 경로 해석, 입력 상태 병합(prefill vs 수동), 숫자 포맷.
- 실행: 백엔드는 `uv run --project backend pytest`(로컬) 또는 Docker dev 스테이지, 프런트는 `npm test`.

## 9. 배포 산출물

snuh-fhir 와 같은 형태: `Dockerfile`(base/frontend/dev/prod), `docker-compose.yaml`, `.env.example`, `README.md`.
런타임 이미지 `python:3.11-slim`, 프런트 빌드 `node:24-alpine`.

## 10. 범위 밖

- 계산 결과 저장·이력, 사용자 인증(상위 gateway 가 담당), 투약(MedicationRequest) 자동 조회(snuh-fhir 미제공),
  LOINC 매핑.
