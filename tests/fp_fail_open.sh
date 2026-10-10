#!/usr/bin/env bash
# Fail-open probe: try to open ~/demo/.ssh/id_rsa once per second and
# record the result with a timestamp. Leave this running, then kill the
# daemon in the other terminal the way the label says.
#
#   bash tests/fp_fail_open.sh <kill9|ctrlc>
#
# Output: results/fp/raw/fail_open_<label>.log

set -uo pipefail

LABEL="${1:-}"
if [ "$LABEL" != "kill9" ] && [ "$LABEL" != "ctrlc" ]; then
    echo "usage: bash tests/fp_fail_open.sh <kill9|ctrlc>"
    exit 1
fi

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/demo/.ssh/id_rsa"
OUT="$HERE/results/fp/raw/fail_open_${LABEL}.log"

if [ ! -e "$TARGET" ]; then
    echo "missing $TARGET — create the demo key file first"
    exit 1
fi

if ! pgrep -f "daemon.py" >/dev/null; then
    echo "The daemon is not running. Start it first."
    exit 1
fi

mkdir -p "$(dirname "$OUT")"
: > "$OUT"

echo "writing $OUT"
echo "target $TARGET"
echo "daemon: $(pgrep -af 'python3 -u daemon.py' | tr '\n' ';')"
echo "kill the daemon now ($LABEL). Ctrl+C this loop when you have ~10 lines after the kill."
echo

n=0
while true; do
    n=$((n + 1))
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    if msg=$(cat "$TARGET" 2>&1); then
        echo "$ts  try=$n  OPENED  bytes=${#msg}"
        echo "$ts  try=$n  OPENED  bytes=${#msg}" >> "$OUT"
    else
        echo "$ts  try=$n  FAILED  $msg"
        echo "$ts  try=$n  FAILED  $msg" >> "$OUT"
    fi
    sleep 1
done
