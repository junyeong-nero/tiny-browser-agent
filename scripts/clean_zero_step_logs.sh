#!/usr/bin/env bash
set -euo pipefail

# Delete session folders under logs/history whose step count is 0
# (i.e. no history/step-*.json files), or whose recorded query is the
# placeholder "test_query". Pass --dry-run to preview.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HISTORY_DIR="${ROOT_DIR}/logs/history"

DRY_RUN=0
for arg in "$@"; do
	case "${arg}" in
		-n|--dry-run) DRY_RUN=1 ;;
		-h|--help)
			echo "Usage: $(basename "$0") [--dry-run]"
			exit 0
			;;
		*)
			echo "Unknown option: ${arg}" >&2
			exit 2
			;;
	esac
done

if [[ ! -d "${HISTORY_DIR}" ]]; then
	echo "No logs/history directory at ${HISTORY_DIR}; nothing to do."
	exit 0
fi

removed=0
kept=0
has_test_query() {
	local session="$1"
	grep -Eq '"query"[[:space:]]*:[[:space:]]*"test_query"' \
		"${session}session.json" "${session}events.jsonl" 2>/dev/null
}

for session in "${HISTORY_DIR}"/*/; do
	[[ -d "${session}" ]] || continue
	if [[ -d "${session}history" ]]; then
		step_count=$(find "${session}history" -maxdepth 1 -name 'step-*.json' -type f | wc -l | tr -d ' ')
	else
		step_count=0
	fi
	remove_reason=""
	if [[ "${step_count}" == "0" ]]; then
		remove_reason="zero steps"
	elif has_test_query "${session}"; then
		remove_reason="test_query"
	fi

	if [[ -n "${remove_reason}" ]]; then
		if (( DRY_RUN )); then
			echo "would remove (${remove_reason}): ${session}"
		else
			echo "removing (${remove_reason}): ${session}"
			rm -rf "${session}"
		fi
		removed=$((removed + 1))
	else
		kept=$((kept + 1))
	fi
done

if (( DRY_RUN )); then
	echo "dry-run: ${removed} folder(s) would be removed, ${kept} kept."
else
	echo "done: ${removed} folder(s) removed, ${kept} kept."
fi
