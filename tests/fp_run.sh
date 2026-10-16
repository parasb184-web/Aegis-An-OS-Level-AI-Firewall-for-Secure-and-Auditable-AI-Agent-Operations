#!/usr/bin/env bash
# False-positive test: runs ordinary developer commands inside a real repo
# while the daemon is running, and records what the daemon did to them.
#
#   PGPASSWORD=... bash tests/fp_run.sh <label> <wait|nowait>
#
#   label   before / after, used in the output folder name
#   wait    15 s pause between commands, so the 10 s risk window empties
#   nowait  commands back to back
#
# Raw output goes to results/fp/raw/<label>_<mode>/.
#
# Opens are matched to commands by PID, not by time: the actions.ts column
# is filled in when the writer thread inserts its batch, which can be a
# couple of seconds after the decision.

set -uo pipefail

LABEL="${1:-}"
MODE="${2:-}"
if [ -z "$LABEL" ] || { [ "$MODE" != "wait" ] && [ "$MODE" != "nowait" ]; }; then
    echo "usage: PGPASSWORD=... bash tests/fp_run.sh <label> <wait|nowait>"
    exit 1
fi

HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$HOME/demo/project/realrepo"
OUT="$HERE/results/fp/raw/${LABEL}_${MODE}"
GAP=15
DSN="host=localhost dbname=aegis user=aegis"

psql_q() { psql "$DSN" -v ON_ERROR_STOP=1 -At -c "$1"; }

if ! pgrep -f "daemon.py" >/dev/null; then
    echo "The daemon is not running. Start it first."
    exit 1
fi
if [ ! -d "$REPO/.git" ]; then
    echo "No repo at $REPO. Run tests/fp_setup.sh first."
    exit 1
fi
if ! psql_q "SELECT 1" >/dev/null; then
    echo "Cannot reach PostgreSQL. Set PGPASSWORD (or ~/.pgpass) and retry."
    exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

# Keep runs comparable: no __pycache__ or .pytest_cache left behind, since
# those land in new, unwatched folders and change what the next run opens.
export PYTHONDONTWRITEBYTECODE=1

CMDS=(
    'git status'
    'git log -5'
    'grep -r "import" .'
    'find . -name "*.py"'
    'ls -R'
    'env PYTHONPATH=src python3 -m pytest --collect-only -q -p no:cacheprovider'
)

cd "$REPO" || exit 1

{
    echo "label: $LABEL"
    echo "mode: $MODE"
    echo "repo: $(git remote get-url origin) @ $(git describe --tags 2>/dev/null) ($(git rev-parse HEAD))"
    echo "host: $(uname -r)"
    echo "daemon: $(pgrep -af daemon.py | tr '\n' ';')"
    echo "pytest: $(python3 -m pytest --version 2>&1 | head -1)"
} > "$OUT/meta.txt"

echo "settling for ${GAP}s so the risk window starts empty"
sleep "$GAP"

DB_START=$(psql_q "SELECT now()::timestamp")
echo "db_start: $DB_START" >> "$OUT/meta.txt"

printf "n\tcommand\tpid\tstart_utc\tend_utc\truntime_s\texit\teperm_lines\n" > "$OUT/commands.tsv"

n=0
for cmd in "${CMDS[@]}"; do
    n=$((n + 1))
    if [ "$MODE" = "wait" ] && [ "$n" -gt 1 ]; then
        sleep "$GAP"
    fi

    start_utc=$(date -u +%H:%M:%S.%3N)
    t0=$(date +%s.%N)
    # exec keeps the PID of the real command, so its rows can be found.
    bash -c "exec $cmd" > "$OUT/$n.stdout" 2> "$OUT/$n.stderr" &
    pid=$!
    wait "$pid"
    status=$?
    t1=$(date +%s.%N)
    end_utc=$(date -u +%H:%M:%S.%3N)

    runtime=$(awk "BEGIN { print $t1 - $t0 }")
    # FAN_DENY reaches the program as EPERM, "Operation not permitted".
    eperm=$(cat "$OUT/$n.stdout" "$OUT/$n.stderr" |
            grep -ciE "operation not permitted|permission denied|EPERM")

    printf "%s\t%s\t%s\t%s\t%s\t%.3f\t%s\t%s\n" \
        "$n" "$cmd" "$pid" "$start_utc" "$end_utc" "$runtime" "$status" "$eperm" \
        >> "$OUT/commands.tsv"
    echo "[$n] $cmd  pid=$pid exit=$status eperm=$eperm ${runtime}s"
done

# The writer flushes every 2 s; give it time before we count.
sleep 5
DB_END=$(psql_q "SELECT now()::timestamp")
echo "db_end: $DB_END" >> "$OUT/meta.txt"

WINDOW="ts BETWEEN '$DB_START' AND '$DB_END'"

printf "n\tcommand\tpid\tblocked_opens\ttotal_opens\texit\teperm_lines\truntime_s\n" > "$OUT/summary.tsv"
tail -n +2 "$OUT/commands.tsv" | while IFS=$'\t' read -r n cmd pid s e rt status eperm; do
    counts=$(psql_q "SELECT count(*) FILTER (WHERE verdict = 'block'), count(*)
                     FROM actions WHERE pid = $pid AND $WINDOW")
    blocked=${counts%|*}
    total=${counts#*|}
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$n" "$cmd" "$pid" "$blocked" "$total" "$status" "$eperm" "$rt" >> "$OUT/summary.tsv"
done

# Every block row in the test window, whoever caused it.
psql "$DSN" -v ON_ERROR_STOP=1 -c "\copy (
    SELECT id, ts, pid, process_name, path, verdict, reason FROM actions
    WHERE verdict = 'block' AND $WINDOW ORDER BY id) TO '$OUT/blocks.csv' CSV HEADER"

# All activity in the window by process, to spot anything not ours.
psql_q "SELECT pid, process_name, verdict, count(*) FROM actions
        WHERE $WINDOW GROUP BY 1, 2, 3 ORDER BY 1, 3" > "$OUT/by_pid.txt"

# The reason on the first block of each command shows what tripped it.
psql_q "SELECT DISTINCT ON (pid) pid, process_name, path, reason FROM actions
        WHERE verdict = 'block' AND $WINDOW ORDER BY pid, id" > "$OUT/first_block.txt"

echo
column -t -s $'\t' "$OUT/summary.tsv" 2>/dev/null || cat "$OUT/summary.tsv"
echo
echo "raw output in $OUT"
