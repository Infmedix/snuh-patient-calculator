#!/usr/bin/env sh
# 반출측: 운영 이미지 빌드 + tar 저장. 태그 규칙 = 당일 YYMMDD + v1, v2… (":latest" 금지)
#
#   sh deploy/build-and-save.sh 261007v1        # → dist/snuh-patient-calculator-261007v1.tar
#
# 다음 단계: 업로더 ① (/upload) 에 tar 드롭 (project=snuh-patient-calculator, tag=261007v1)
#            → registry.internal/airgap/snuh-patient-calculator:261007v1
#            deploy/argo/kustomization.yaml 의 newTag 를 같은 값으로.
# 프런트 빌드 스테이지가 node:24-alpine 을 당기므로 빌드 머신은 인터넷(또는 미러)이 필요하다.
set -eu

TAG="${1:?태그를 지정하세요 (예: 261007v1)}"
IMAGE="snuh-patient-calculator:${TAG}"
cd "$(dirname "$0")/.."
mkdir -p dist
OUT="dist/snuh-patient-calculator-${TAG}.tar"

echo "[build] ${IMAGE}"
docker build --target prod -t "${IMAGE}" .
echo "[save] ${OUT}"
docker save "${IMAGE}" -o "${OUT}"
ls -lh "${OUT}"
