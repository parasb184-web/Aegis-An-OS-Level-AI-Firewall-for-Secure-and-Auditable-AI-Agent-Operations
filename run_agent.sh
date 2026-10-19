#!/usr/bin/env bash
set -e

ROOTS=${AEGIS_ROOTS:-/tmp/aegis_roots}

if [ $# -ne 1 ]; then
    echo "usage: ./run_agent.sh [normal|credentials|massread]"
    exit 1
fi

echo $$ >> "$ROOTS"
exec python3 fake_agent.py "$1"
