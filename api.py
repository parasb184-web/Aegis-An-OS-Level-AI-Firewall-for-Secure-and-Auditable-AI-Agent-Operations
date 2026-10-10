# Small web server that reads the audit log for the dashboard.
# It only reads. All the deciding happens in daemon.py.

from fastapi import FastAPI
from fastapi.responses import FileResponse

import db

app = FastAPI()


@app.get("/counts")
def counts():
    conn = db.connect()
    cur = conn.cursor()
    # Read the trigger-maintained totals instead of counting the whole log
    # on every dashboard poll. See sql/counts_table.sql.
    cur.execute("SELECT verdict, n FROM verdict_counts")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {"allow": 0, "block": 0, "warn": 0}
    for verdict, count in rows:
        result[verdict] = count
    return result


@app.get("/recent")
def recent():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, process_name, path, verdict, reason "
        "FROM actions ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    for ts, process_name, path, verdict, reason in rows:
        out.append({
            "time": ts.strftime("%H:%M:%S"),
            "process": process_name,
            "path": path,
            "verdict": verdict,
            "reason": reason,
        })
    return out


@app.get("/")
def dashboard():
    return FileResponse("dashboard.html")