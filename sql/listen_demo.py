# Prototype of live policy reload: wait for NOTIFY policies_changed and
# reload the rules when it arrives. Not wired into daemon.py.
#
#   python3 sql/listen_demo.py
#   (then INSERT/UPDATE/DELETE a row in policies from psql)

import os
import select
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

conn = db.connect()
# Notifications are only handed to us between transactions, so we must not
# sit inside an open one.
conn.autocommit = True
cur = conn.cursor()
cur.execute("LISTEN policies_changed")

policies = db.load_policies()
print("loaded %d rules, waiting for changes" % len(policies), flush=True)

while True:
    # Sleep until the server sends something; no polling the table.
    if select.select([conn], [], [], 60) == ([], [], []):
        continue
    conn.poll()
    while conn.notifies:
        n = conn.notifies.pop(0)
        print("notify %s: %s" % (n.channel, n.payload), flush=True)
    # One reload covers however many notifications arrived together.
    policies = db.load_policies()
    print("reloaded %d rules" % len(policies), flush=True)
