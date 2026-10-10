# Insert cost with and without the verdict_counts trigger, done the way
# writer.py does it: one INSERT per row, commit every 50 rows.
#
# Uses actions_exp (same columns as actions, 2M rows) because these rows
# really commit, and we do not want 120,000 fake rows on the live dashboard.
# Needs sql/generate_dataset.sql and sql/trigger_cost.sql to have run.
#
#   python3 sql/insert_bench.py > results/db/task5_python.txt

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

ROWS = 10000
BATCH = 50
ROUNDS = 6


def insert_rows(conn, cur):
    start = time.perf_counter()
    for i in range(ROWS):
        verdict = "block" if i % 20 == 0 else "warn" if i % 20 == 10 else "allow"
        cur.execute(
            "INSERT INTO actions_exp (pid, process_name, path, verdict, reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, "bench", "/home/kusha/demo/project/src/f%d.py" % (i % 500),
             verdict, "bench"))
        if (i + 1) % BATCH == 0:
            conn.commit()
    conn.commit()
    return (time.perf_counter() - start) * 1000


def set_trigger(cur, on):
    word = "ENABLE" if on else "DISABLE"
    cur.execute("ALTER TABLE actions_exp %s TRIGGER actions_exp_count_verdict" % word)


conn = db.connect()
cur = conn.cursor()
results = {"trigger_on": [], "trigger_off": []}

# Alternate on/off each round so slow drift affects both equally.
for r in range(1, ROUNDS + 1):
    for name in ["trigger_on", "trigger_off"]:
        set_trigger(cur, name == "trigger_on")
        conn.commit()
        ms = insert_rows(conn, cur)
        print("round %d %-11s %9.1f ms" % (r, name, ms), flush=True)
        if r > 1:
            results[name].append(ms)

        # Clear out old counter-row versions so each round starts alike.
        # Bench rows stay in actions_exp until the end: deleting them here
        # is very slow (see sql/fk_delete_check.sql).
        conn.autocommit = True
        cur.execute("VACUUM verdict_counts_exp")
        conn.autocommit = False

set_trigger(cur, True)
conn.commit()

# Remove the bench rows (pid 0 is never used by the dataset). A temporary
# index on parent_action makes the foreign key check on each deleted row
# an index lookup instead of a scan of the whole table.
cur.execute("CREATE INDEX bench_parent ON actions_exp (parent_action)")
cur.execute("DELETE FROM actions_exp WHERE pid = 0")
cur.execute("DROP INDEX bench_parent")
conn.commit()

print()
print("%d rows, commit every %d, median of rounds 2-%d:" % (ROWS, BATCH, ROUNDS))
for name in ["trigger_on", "trigger_off"]:
    print("  %-11s %9.1f ms" % (name, statistics.median(results[name])))
on = statistics.median(results["trigger_on"])
off = statistics.median(results["trigger_off"])
print("  overhead    %9.1f ms total, %.1f us per row, %.1f%%" % (
    on - off, (on - off) * 1000 / ROWS, (on - off) * 100 / off))
cur.close()
conn.close()
