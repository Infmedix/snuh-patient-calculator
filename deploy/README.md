# snuh-patient-calculator 배포 (`deploy/`)

폐쇄망 k3s GitOps 규격(snuh-fhir-web `deploy/README.md` 와 동일)에 맞춘 매니페스트 세트. **이 README 는 zip 에 넣지 않는다.**

- app=`snuh-patient-calculator` · ns=`platform` · port=`8000` · 노드 제약 없음 · PVC 없음
- 이미지: `registry.internal/airgap/snuh-patient-calculator:<tag>` (단일 커스텀 이미지)
- 데이터: 같은 ns 의 `snuh-fhir-web` Service (클러스터 내부 호출). FHIR 호출 자격은 `config.env` 의 서비스 계정 PAT(`APP_FHIR_TOKEN`, 관리자가 발급). 비우면 사용자 본인 PAT 를 화면에서 등록

## 구성 파일 (`deploy/argo/`)

| 파일 | 내용 |
|---|---|
| `kustomization.yaml` | resources + `configMapGenerator`(config.env) + 이미지 태그 `newTag` |
| `deployment.yaml` | 앱 본체. RollingUpdate 무중단, liveness·readiness 모두 `/api/health` (fhir 장애가 502 로 번지지 않게 readiness 는 fhir 왕복을 하지 않는다) |
| `service.yaml` | ClusterIP `snuh-patient-calculator:8000` — 프록시 env 의 upstream |
| `config.env` | 환경변수 전부 (k8s Secret 미사용) |

## 절차 — 테스트 서버(192.168.0.50) / 원내 동일

```bash
# 1) 이미지 — 태그 = 당일 YYMMDD + v1, v2…  (deploy/build-and-save.sh 가 빌드·save 를 한다)
TAG=261007v4
sh deploy/build-and-save.sh $TAG            # → dist/snuh-patient-calculator-$TAG.tar
#    → 업로더 ① (http://<호스트>/upload): project=snuh-patient-calculator, tag=$TAG
#      → registry.internal/airgap/snuh-patient-calculator:$TAG
#    태그 bump 시 deploy/argo/kustomization.yaml 의 newTag 도 함께 갱신 (":latest" 금지)

# 2) 매니페스트 — deploy/argo/ 의 4개 파일만 zip (zip 루트에 파일이 바로 오게)
cd deploy/argo && zip ../../dist/snuh-patient-calculator-deploy.zip kustomization.yaml config.env deployment.yaml service.yaml
#    → 업로더 ②: app=snuh-patient-calculator, ns=platform (Argo CD auto-sync 는 처음엔 끄고 확인 후 Sync)
#      → GitLab airgap/snuh-patient-calculator (path deploy) + Argo Application

# 3) Argo CD (/argocd) 에서 snuh-patient-calculator Sync → 파드 Ready 확인
#    kubectl -n platform get pods -l app=snuh-patient-calculator
#    kubectl -n platform logs deploy/snuh-patient-calculator    # [Lifespan] FHIR source: http http://snuh-fhir-web…

# 4) apps 플랫폼 콘솔(/deploy) 에서 **프록시 env** 생성 (최초 1회, 이미지·환경변수 없음)
#    앱 snuh-patient-calculator · env 종류 프록시 · slug snuh-patient-calculator
#    upstream http://snuh-patient-calculator.platform.svc.cluster.local:8000 · 헬스체크 /api/health · 인증 parent_gateway
```

업로더 ①② 는 REST 로도 된다 (`scripts/upload-testbed.sh` 참고): `POST /upload/api/sessions`(kind=image) → `PUT …/files/{id}?offset=0` → `POST …/finalize`,
`PUT /upload/manifest?name=&ns=&auto=0|1` (zip 본문).

## 확인

```
http://<포털>/apps/runtime/snuh-patient-calculator/              → 307 → /ui/
http://<포털>/apps/runtime/snuh-patient-calculator/api/health    → {"status":"ok"}
http://<포털>/apps/runtime/snuh-patient-calculator/api/health/ready → {"status":"ok","fhir":"ok"}
```

## 서비스 계정 PAT (`APP_FHIR_TOKEN`)

1. snuh-fhir-web 관리자가 서비스용 계정(예: calculator)으로 로그인 → 「내 토큰」에서 PAT 발급 (이름 `patient-calculator`, 만료 최대 365일).
2. 관리자 「사용자」 탭에서 그 계정에 **FHIR 접근 허용** 부여 (없으면 모든 조회가 `pat_no_access`).
3. 토큰은 **`deploy/argo/secrets.env`**(git 제외)에 `APP_FHIR_TOKEN=<원문>` 으로 둔다. `deploy/upload-testbed.sh` 가 zip 을 만들 때 config.env 의 같은 키를 이 값으로 덮어쓴다 — 저장소의 config.env 는 빈 값 유지. → 업로더 ② → Argo Sync. configMap 해시가 바뀌어 자동 롤아웃.
4. 확인: 화면 상단에 「FHIR 연결됨」 태그, `/api/health/ready` 가 `{"fhir":"ok","token":"service"}`.
5. 만료 전 새 토큰 발급 → 3 반복. 토큰은 GitLab config.env 에 평문으로 들어가므로(테스트베드 §5 정책) 저장소 접근 권한에 유의.

`APP_FHIR_TOKEN` 이 비어 있으면 화면에 PAT 패널이 떠 사용자가 본인 토큰을 등록해 쓸 수 있다(요청 헤더 `X-Fhir-Token` 이 서비스 토큰보다 우선).

## 왜 apps 플랫폼 env 가 아니라 Argo 경로인가

snuh-fhir-web 과 달리 노드 제약이 없어 apps 플랫폼 env(`기존 이미지 주소 사용`: `registry.internal/airgap/snuh-patient-calculator:<tag>`)로도
올릴 수 있다. 그 경우 플랫폼이 `BASE_URL`·`PORT` 를 주입하고 앱이 그대로 수용한다(`APP_PATH_PREFIX` 불필요, 헬스체크 경로 `/api/health`).
Argo 경로를 기본으로 둔 이유는 snuh-fhir-web 과 같은 운영 절차(GitLab 이력·config.env 롤아웃)로 묶기 위해서다.
