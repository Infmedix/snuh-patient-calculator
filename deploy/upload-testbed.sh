#!/usr/bin/env sh
# 테스트 서버 업로더(/upload) REST 로 ① 이미지 적재 ② 매니페스트 등록.
#
#   sh deploy/upload-testbed.sh 261007v1 [http://192.168.0.50] [auto=0|1]
#
# 전제: dist/snuh-patient-calculator-<TAG>.tar (build-and-save.sh). kustomization.yaml 의 newTag(__TAG__)는 zip 에 넣을 때 TAG 로 치환한다.
# ② 는 GitLab airgap/snuh-patient-calculator 저장소와 Argo Application 을 만든다/갱신한다. auto=1 이면 Argo auto-sync.
set -eu

TAG="${1:?태그}"
HOST="${2:-http://192.168.0.50}"
AUTO="${3:-0}"
APP="snuh-patient-calculator"
cd "$(dirname "$0")/.."
TAR="dist/${APP}-${TAG}.tar"
[ -f "${TAR}" ] || { echo "없음: ${TAR} — 먼저 deploy/build-and-save.sh ${TAG}"; exit 1; }

SIZE=$(wc -c < "${TAR}" | tr -d ' ')
echo "[①] 세션 생성 (project=${APP} tag=${TAG} size=${SIZE})"
SESSION=$(curl -sf -X POST "${HOST}/upload/api/sessions" -H 'Content-Type: application/json' \
  -d "{\"kind\":\"image\",\"files\":[{\"path\":\"$(basename "${TAR}")\",\"size\":${SIZE},\"mtime\":null}],\"options\":{\"name\":\"${APP}\",\"image\":\"\",\"tag\":\"${TAG}\",\"multi\":false}}")
# 세션 id 는 응답 맨 앞의 "id". `.*"id"` 처럼 탐욕 매칭하면 files[].id 를 집어 404 가 난다
SID=$(printf '%s' "${SESSION}" | sed -n 's/^[[:space:]]*{[[:space:]]*"id": *"\([^"]*\)".*/\1/p' | head -1)
FID=$(printf '%s' "${SESSION}" | sed -n 's/.*"files": *\[{[^}]*"id": *"\([^"]*\)".*/\1/p' | head -1)
[ -n "${SID}" ] && [ -n "${FID}" ] || { echo "세션 응답 해석 실패: ${SESSION}"; exit 1; }
echo "[①] tar 전송 (session ${SID})"
curl -sf -X PUT "${HOST}/upload/api/sessions/${SID}/files/${FID}?offset=0" --data-binary "@${TAR}" > /dev/null
echo "[①] finalize → registry"
curl -sf -X POST "${HOST}/upload/api/sessions/${SID}/files/${FID}/finalize"
echo

ZIP="dist/${APP}-deploy.zip"
rm -f "${ZIP}"
# config.env 에 secrets.env(git 제외) 의 KEY=VALUE 를 덮어써서 zip 에 넣는다 — 토큰을 저장소에 커밋하지 않기 위해
STAGE="$(mktemp -d)"; cp deploy/argo/deployment.yaml deploy/argo/service.yaml "${STAGE}/"
# kustomization.yaml 의 __TAG__ 를 이번 빌드 태그로 치환 (저장소에는 태그를 커밋하지 않는다)
sed "s/__TAG__/${TAG}/" deploy/argo/kustomization.yaml > "${STAGE}/kustomization.yaml"
if [ -f deploy/argo/secrets.env ]; then
  awk 'FNR==NR { if ($0 !~ /^#/ && index($0,"=")) { k=substr($0,1,index($0,"=")-1); v[k]=$0 } ; next }
       { k=substr($0,1,index($0,"=")-1); if (index($0,"=") && (k in v)) print v[k]; else print }' deploy/argo/secrets.env deploy/argo/config.env > "${STAGE}/config.env"
else
  cp deploy/argo/config.env "${STAGE}/"
fi
# Git Bash 에는 zip 이 없다 → Windows 기본 bsdtar(-a 가 확장자로 zip 형식 선택)로 대체
if command -v zip > /dev/null 2>&1; then
  (cd "${STAGE}" && zip -q "${OLDPWD}/${ZIP}" kustomization.yaml config.env deployment.yaml service.yaml)
else
  /c/Windows/System32/tar.exe -a -c -f "${ZIP}" -C "${STAGE}" kustomization.yaml config.env deployment.yaml service.yaml
fi
rm -rf "${STAGE}"
echo "[②] 매니페스트 등록 (app=${APP} ns=platform auto=${AUTO})"
curl -sf -X PUT "${HOST}/upload/manifest?name=${APP}&ns=platform&auto=${AUTO}" --data-binary "@${ZIP}"
echo
echo "다음: ${HOST}/argocd 에서 ${APP} Sync → ${HOST}/deploy 에서 프록시 env(slug ${APP}) 생성"
