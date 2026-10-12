# Loads the policy rules from PostgreSQL and decides if a path matches one.
#
# We load them ONCE at startup into a plain list, not query the database
# per file open. The process being checked is frozen while we decide, so a
# database round trip on every open would add that delay to every file the
# agent touches.

import fnmatch
import psycopg2

DB = "dbname=aegis user=aegis password=aegis host=localhost"


def connect():
    return psycopg2.connect(DB)


def load_policies():
    conn = connect()
    cur = conn.cursor()
    # check() returns the first match, so the order here is the rule
    # priority. Without ORDER BY, SQL returns rows in whatever order they
    # sit on disk, and an UPDATE can move a row. Blocks come first so a
    # block always beats an allow (a .env inside the project stays
    # blocked); id breaks ties so the order never changes between runs.
    cur.execute("SELECT path_pattern, sensitivity, action, note FROM policies "
                "ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # SQL uses % as its wildcard, fnmatch uses *. We convert once here so
    # the matching in check() is a simple string compare.
    policies = []
    for pattern, sensitivity, action, note in rows:
        policies.append((pattern.replace("%", "*"), sensitivity, action, note))
    return policies


def check(policies, path):
    # Returns (action, reason) for the first rule that matches, or
    # (None, None) if no rule mentions this path at all.
    for pattern, sensitivity, action, note in policies:
        if fnmatch.fnmatch(path, pattern):
            return action, note
    return None, None


if __name__ == "__main__":
    p = load_policies()
    print("loaded %d rules" % len(p))
    for test in ["/home/acerparas/.ssh/id_rsa",
                 "/home/acerparas/project/main.py",
                 "/home/acerparas/notes.txt"]:
        print(test, "->", check(p, test))