#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/run_batch.sh              # run all levels
#   scripts/run_batch.sh hard         # run only hard tasks
#   scripts/run_batch.sh medium --limit 100
#   LEVEL=easy scripts/run_batch.sh

LEVEL="${LEVEL:-all}"
if [[ -z "${LEVEL:-}" ]]; then
	LEVEL="all"
fi

if [[ $# -gt 0 && ( "$1" == "easy" || "$1" == "medium" || "$1" == "hard" || "$1" == "all" ) ]]; then
	LEVEL="$1"
	shift
fi

if [[ "$LEVEL" != "easy" && "$LEVEL" != "medium" && "$LEVEL" != "hard" && "$LEVEL" != "all" ]]; then
	echo "Usage: $0 [all|easy|medium|hard] [batch_runner args...]" >&2
	exit 2
fi

LEVEL_ARGS=()
if [[ "$LEVEL" != "all" ]]; then
	LEVEL_ARGS=(--level "$LEVEL")
fi

uv run python scripts/batch_runner.py \
	--dataset junyeong-nero/korean-online-mind2web \
	--limit 500 \
	--workers 1 \
	--metadata-initial-url \
	--log-agent \
	--extra-arg=--stealth \
	--extra-arg=--locale=ko-KR \
	--extra-arg=--timezone=Asia/Seoul \
	'--extra-arg=--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' \
	"${LEVEL_ARGS[@]}" \
	"$@"
