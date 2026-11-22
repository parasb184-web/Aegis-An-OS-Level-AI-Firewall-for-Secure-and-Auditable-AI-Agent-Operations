import fnmatch
import psycopg2

DB = "dbname=aegis user=aegis password=aegis host=localhost"


def connect():
    return psycopg2.connect(DB)


def load_policies():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT path_pattern, sensitivity, action, note FROM policies "
                "ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    policies = []
    for pattern, sensitivity, action, note in rows:
        policies.append((pattern.replace("%", "*"), sensitivity, action, note))
    return policies


def check(policies, path):
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
