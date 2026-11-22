
import os
import select
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

conn = db.connect()

conn.autocommit = True
cur = conn.cursor()
cur.execute("LISTEN policies_changed")

policies = db.load_policies()
print("loaded %d rules, waiting for changes" % len(policies), flush=True)

while True:
    if select.select([conn], [], [], 60) == ([], [], []):
        continue
    conn.poll()
    while conn.notifies:
        n = conn.notifies.pop(0)
        print("notify %s: %s" % (n.channel, n.payload), flush=True)
    policies = db.load_policies()
    print("reloaded %d rules" % len(policies), flush=True)
