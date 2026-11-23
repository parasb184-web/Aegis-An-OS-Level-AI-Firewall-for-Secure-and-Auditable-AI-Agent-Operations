import sys
sys.path.insert(0, "/home/kusha/aegis")
import db
p = db.load_policies()
print([x[0] for x in p])
for t in ["/home/kusha/demo/project/.env", "/home/kusha/demo/project/src/app.py"]:
    print(t, "->", db.check(p, t))
