#!/usr/bin/env python3
"""Aegis Database Health Check.

Verifies PostgreSQL connectivity, schema tables, triggers, and current decision
record counts.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import db


def main():
    print("[Aegis DB Check] Connecting to PostgreSQL...")
    try:
        conn = db.connect()
    except Exception as e:
        print(f"[Error] Failed to connect: {e}")
        print("Ensure PostgreSQL is running and credentials in db.py / AEGIS_DB are valid.")
        sys.exit(1)

    cur = conn.cursor()
    print("[Aegis DB Check] Connected successfully.")

    # 1. Verify tables
    expected_tables = ["policies", "actions", "verdict_counts"]
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    existing_tables = {row[0] for row in cur.fetchall()}

    all_ok = True
    for t in expected_tables:
        if t in existing_tables:
            print(f"  [OK] Table '{t}' exists.")
        else:
            print(f"  [MISSING] Table '{t}' not found! Run: psql -d aegis -f schema.sql")
            all_ok = False

    # 2. Verify trigger
    cur.execute("""
        SELECT trigger_name 
        FROM information_schema.triggers 
        WHERE event_object_table = 'actions'
    """)
    triggers = {row[0] for row in cur.fetchall()}
    if "actions_count_verdict" in triggers:
        print("  [OK] Trigger 'actions_count_verdict' is active.")
    else:
        print("  [WARN] Trigger 'actions_count_verdict' missing from actions table.")

    # 3. Report record counts
    if "policies" in existing_tables:
        cur.execute("SELECT count(*) FROM policies")
        print(f"  Policies configured: {cur.fetchone()[0]}")

    if "verdict_counts" in existing_tables:
        cur.execute("SELECT verdict, n FROM verdict_counts")
        counts = dict(cur.fetchall())
        print(f"  Current counts: Allow={counts.get('allow', 0)}, "
              f"Block={counts.get('block', 0)}, Warn={counts.get('warn', 0)}")

    cur.close()
    conn.close()

    if all_ok:
        print("[Aegis DB Check] Database is fully operational.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
