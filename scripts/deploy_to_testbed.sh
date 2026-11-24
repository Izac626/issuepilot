#!/bin/sh
# IssuePilot을 대상 저장소의 .issuepilot/ 와 워크플로 1개로 설치하고 푸시한다.
#   scripts/deploy_to_testbed.sh [대상 저장소 로컬 경로]
# 배포 전에 린트와 단위 테스트를 통과해야 한다.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-$HERE/../issuepilot-testbed}"
[ -d "$TARGET/.git" ] || { echo "대상 저장소가 없습니다: $TARGET" >&2; exit 1; }

"$HERE/.venv/bin/python" -m ruff check "$HERE" -q
"$HERE/.venv/bin/python" -m pytest "$HERE/tests" -q

mkdir -p "$TARGET/.issuepilot" "$TARGET/.github/workflows"
rm -rf "$TARGET/.issuepilot/src"   # 이전 구조 정리
rsync -a --delete --exclude '__pycache__' "$HERE/issuepilot" "$TARGET/.issuepilot/"
cp "$HERE/requirements-run.txt" "$TARGET/.issuepilot/"
cp "$HERE/deploy/issue-pilot.yml" "$TARGET/.github/workflows/issue-pilot.yml"

cd "$TARGET"
git add .issuepilot .github
if git diff --cached --quiet; then echo "변경 없음"; exit 0; fi
# 배포물에 비밀 값이 섞이지 않았는지 확인
if git diff --cached | grep -E -q 'sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}'; then
  echo "배포 중단: 변경분에 키로 보이는 문자열이 있습니다" >&2; git reset -q; exit 1
fi
git commit -q -m "IssuePilot 배포 $(date '+%Y-%m-%d %H:%M')"
git push -q
echo "배포 완료: $(git log -1 --format=%h)"
