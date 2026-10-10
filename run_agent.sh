#!/usr/bin/env bash
# Starts the fake agent as a process Aegis supervises.
#
# We append our own pid to the roots file and then exec. exec replaces this
# shell rather than forking, so the pid we just registered is the pid the
# agent actually runs under, and everything the agent starts is a child of it.

set -e

ROOTS=${AEGIS_ROOTS:-/tmp/aegis_roots}

if [ $# -ne 1 ]; then
    echo "usage: ./run_agent.sh [normal|credentials|massread]"
    exit 1
fi

echo $$ >> "$ROOTS"
exec python3 fake_agent.py "$1"
